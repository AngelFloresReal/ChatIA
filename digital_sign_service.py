"""
Módulo de firma digital de documentos usando IronPDF.

Permite firmar archivos PDF directamente y genera representaciones
firmables para archivos de texto (.txt, .md, .log) y comprimidos (.zip)
añadiendo metadatos de integridad y adjuntando el archivo original dentro
del PDF antes de aplicar la firma digital.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

try:
    from ironpdf import HtmlToPdf, PdfDocument
    try:
        # Firmas avanzadas (alias signing en versiones recientes)
        from ironpdf import signing as iron_signing
    except ImportError:  # pragma: no cover - compatibilidad
        iron_signing = None
except ImportError as exc:  # pragma: no cover - ambiente sin IronPDF
    HtmlToPdf = None
    PdfDocument = None
    iron_signing = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from config_oauth import (
    IRONPDF_CERTIFICATE_PATH,
    IRONPDF_CERTIFICATE_PASSWORD,
    IRONPDF_LICENSE_KEY,
)


class IronPdfUnavailable(RuntimeError):
    """Se lanza cuando IronPDF no está instalado en el entorno."""


def _ensure_ironpdf_available():
    if PdfDocument is None or HtmlToPdf is None:
        raise IronPdfUnavailable(
            "La librería 'ironpdf' no está instalada. "
            "Instala con 'pip install ironpdf pythonnet' y asegúrate de tener "
            "una licencia válida."
        ) from _IMPORT_ERROR


def _load_license(license_key: Optional[str]):
    if not license_key:
        return
    try:  # pragma: no cover - depende de licencias reales
        from ironpdf import License

        License.LicenseKey = license_key
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"No se pudo aplicar la licencia de IronPDF: {exc}") from exc


def _human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} TB"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class SignatureMetadata:
    reason: str
    location: str
    contact: str


class DigitalSignService:
    """
    Servicio de firma usando IronPDF.

    Ejemplo:
        signer = DigitalSignService(
            certificate_path="certs/certificado.pfx",
            certificate_password="SuperSecreto",
        )
        signer.sign_files(["contrato.pdf", "evidencia.zip"], output_dir="firmados")
    """

    def __init__(
        self,
        certificate_path: Optional[str] = None,
        certificate_password: Optional[str] = None,
        *,
        license_key: Optional[str] = None,
    ):
        _ensure_ironpdf_available()
        _load_license(license_key or IRONPDF_LICENSE_KEY or None)

        self.certificate_path = Path(
            certificate_path or IRONPDF_CERTIFICATE_PATH
        ).expanduser()
        self.certificate_password = (
            certificate_password or IRONPDF_CERTIFICATE_PASSWORD or None
        )

        if not self.certificate_path.exists():
            raise FileNotFoundError(
                f"No se encontró el certificado PFX para firmar: {self.certificate_path}"
            )
        if not self.certificate_password:
            raise ValueError("Se requiere la contraseña del certificado PFX.")

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def sign_files(
        self,
        sources: Iterable[str],
        *,
        output_dir: Optional[str] = None,
        metadata: Optional[SignatureMetadata] = None,
        attach_original: bool = True,
    ) -> List[Path]:
        signed_files: List[Path] = []
        for src in sources:
            signed_files.append(
                self.sign_file(
                    src,
                    output_dir=output_dir,
                    metadata=metadata,
                    attach_original=attach_original,
                )
            )
        return signed_files

    def sign_file(
        self,
        source_path: str,
        *,
        output_dir: Optional[str] = None,
        metadata: Optional[SignatureMetadata] = None,
        attach_original: bool = True,
    ) -> Path:
        metadata = metadata or SignatureMetadata(
            reason="Aprobación de contenido",
            location="Remoto",
            contact="N/A",
        )
        source = Path(source_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(source)

        pdf_doc = self._build_pdf_from_source(source, attach_original=attach_original)
        self._apply_signature(pdf_doc, metadata)

        destination = self._resolve_output_path(source, output_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        pdf_doc.SaveAs(destination.as_posix())
        return destination

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _resolve_output_path(self, source: Path, output_dir: Optional[str]) -> Path:
        target_dir = Path(output_dir).expanduser().resolve() if output_dir else source.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{source.stem}_firmado.pdf"

    def _build_pdf_from_source(self, source: Path, *, attach_original: bool) -> "PdfDocument":
        ext = source.suffix.lower()
        if ext == ".pdf":
            pdf_doc = PdfDocument.FromFile(source.as_posix())
            if attach_original and hasattr(pdf_doc, "AttachFile"):
                pdf_doc.AttachFile(source.as_posix())
            return pdf_doc

        renderer = HtmlToPdf()
        if ext in {".txt", ".md", ".log"}:
            html = self._render_text_file(source)
        elif ext == ".zip":
            html = self._render_zip_summary(source)
        else:
            html = self._render_generic_file(source)

        pdf_doc = renderer.RenderHtmlAsPdf(html)
        if attach_original and hasattr(pdf_doc, "AttachFile"):
            pdf_doc.AttachFile(source.as_posix())
        return pdf_doc

    def _render_text_file(self, source: Path) -> str:
        content = source.read_text(encoding="utf-8", errors="replace")
        escaped = (
            content.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        checksum = _sha256(source)
        return f"""
        <html>
            <head>
                <meta charset="utf-8"/>
                <style>
                    body {{ font-family: 'Fira Code', monospace; }}
                    pre {{
                        background: #f7f9fb;
                        padding: 16px;
                        border-radius: 8px;
                        white-space: pre-wrap;
                    }}
                </style>
            </head>
            <body>
                <h1>Documento de texto firmado</h1>
                <p><strong>Archivo:</strong> {source.name}</p>
                <p><strong>SHA-256:</strong> {checksum}</p>
                <hr/>
                <pre>{escaped}</pre>
            </body>
        </html>
        """

    def _render_zip_summary(self, source: Path) -> str:
        rows = []
        with zipfile.ZipFile(source, "r") as zf:
            for info in zf.infolist():
                rows.append(
                    f"<tr><td>{info.filename}</td>"
                    f"<td>{_human_size(info.file_size)}</td>"
                    f"<td>{info.date_time[0]}-{info.date_time[1]:02}-{info.date_time[2]:02}</td></tr>"
                )
        checksum = _sha256(source)
        return f"""
        <html>
            <head>
                <meta charset="utf-8"/>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                    }}
                    th, td {{
                        border: 1px solid #ddd;
                        padding: 8px;
                    }}
                    th {{ background: #f2f2f2; }}
                </style>
            </head>
            <body>
                <h1>Resumen de ZIP para firma digital</h1>
                <p><strong>Archivo:</strong> {source.name}</p>
                <p><strong>SHA-256:</strong> {checksum}</p>
                <table>
                    <thead>
                        <tr><th>Contenido</th><th>Tamaño</th><th>Fecha</th></tr>
                    </thead>
                    <tbody>
                        {''.join(rows) or '<tr><td colspan="3">ZIP vacío</td></tr>'}
                    </tbody>
                </table>
            </body>
        </html>
        """

    def _render_generic_file(self, source: Path) -> str:
        checksum = _sha256(source)
        encoded_sample = self._read_file_sample(source)
        return f"""
        <html>
            <head>
                <meta charset="utf-8"/>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    code {{
                        display: block;
                        background: #272822;
                        color: #f8f8f2;
                        padding: 12px;
                        border-radius: 8px;
                        white-space: pre-wrap;
                    }}
                </style>
            </head>
            <body>
                <h1>Representación firmable de {source.name}</h1>
                <p>Se incluye un extracto codificado en Base64 para garantizar integridad.</p>
                <ul>
                    <li><strong>Ruta:</strong> {source}</li>
                    <li><strong>Tamaño:</strong> {_human_size(source.stat().st_size)}</li>
                    <li><strong>SHA-256:</strong> {checksum}</li>
                </ul>
                <h3>Preview Base64</h3>
                <code>{encoded_sample}</code>
            </body>
        </html>
        """

    def _read_file_sample(self, source: Path, limit: int = 4096) -> str:
        with source.open("rb") as f:
            sample = f.read(limit)
        return base64.b64encode(sample).decode("ascii")

    def _apply_signature(self, pdf_doc: "PdfDocument", metadata: SignatureMetadata):
        if iron_signing and hasattr(iron_signing, "DigitalSignature"):
            signature = iron_signing.DigitalSignature(
                certificate_path=self.certificate_path.as_posix(),
                certificate_password=self.certificate_password,
            )
            signature.contact_info = metadata.contact
            signature.location = metadata.location
            signature.reason = metadata.reason
            pdf_doc.ApplyDigitalSignature(signature)
            return

        # Fallback para versiones antiguas
        if hasattr(pdf_doc, "ApplyDigitalSignature"):
            pdf_doc.ApplyDigitalSignature(
                self.certificate_path.as_posix(), self.certificate_password
            )
            return

        raise RuntimeError(
            "La versión instalada de IronPDF no soporta ApplyDigitalSignature."
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Firma digital de archivos (PDF/TXT/ZIP) usando IronPDF."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Rutas de los archivos a firmar.",
    )
    parser.add_argument(
        "--cert",
        dest="certificate",
        help="Ruta al certificado PFX. Por defecto usa config_oauth.IRONPDF_CERTIFICATE_PATH.",
    )
    parser.add_argument(
        "--password",
        dest="password",
        help="Contraseña del certificado PFX.",
    )
    parser.add_argument(
        "--out",
        dest="output_dir",
        help="Directorio de salida (se conserva la carpeta origen si no se especifica).",
    )
    parser.add_argument("--reason", default="Aprobación documental")
    parser.add_argument("--location", default="Infraestructura en la nube")
    parser.add_argument("--contact", default="legal@example.com")
    parser.add_argument(
        "--skip-attachment",
        action="store_true",
        help="No adjuntar el archivo original dentro del PDF.",
    )
    parser.add_argument(
        "--license-key",
        help="Clave de licencia de IronPDF (override de config).",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    metadata = SignatureMetadata(
        reason=args.reason,
        location=args.location,
        contact=args.contact,
    )

    signer = DigitalSignService(
        certificate_path=args.certificate,
        certificate_password=args.password,
        license_key=args.license_key,
    )
    signed = signer.sign_files(
        args.files,
        output_dir=args.output_dir,
        metadata=metadata,
        attach_original=not args.skip_attachment,
    )

    print("✓ Firma completada:")
    for path in signed:
        print(f"  - {path}")


if __name__ == "__main__":  # pragma: no cover
    main()

