"""
Servidor ligero para subir archivos y firmarlos usando IronPDF.
Diseñado para ejecutarse en AWS (EC2, Lightsail) o cualquier VM.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from cloud_workflow import CloudSigningWorkflow
from config_oauth import (
    AUTHORIZED_SIGNER_EMAILS,
    IRONPDF_CERTIFICATE_PASSWORD,
    IRONPDF_CERTIFICATE_PATH,
)
from digital_sign_service import DigitalSignService, SignatureMetadata

app = Flask(__name__)


def build_signer() -> DigitalSignService:
    return DigitalSignService(
        certificate_path=os.getenv("SIGNER_CERT_PATH", IRONPDF_CERTIFICATE_PATH),
        certificate_password=os.getenv(
            "SIGNER_CERT_PASSWORD", IRONPDF_CERTIFICATE_PASSWORD
        ),
        license_key=os.getenv("IRONPDF_LICENSE_KEY"),
    )


def build_workflow() -> CloudSigningWorkflow:
    return CloudSigningWorkflow()


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/sign")
def sign_endpoint():
    if "file" not in request.files:
        return jsonify({"error": "Falta 'file' en multipart/form-data"}), 400

    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "Archivo sin nombre"}), 400

    signer = build_signer()
    workflow = build_workflow()

    metadata = SignatureMetadata(
        reason=request.form.get("reason", "Autorización remota"),
        location=request.form.get("location", "Infraestructura AWS/VM"),
        contact=request.form.get("contact", ",".join(AUTHORIZED_SIGNER_EMAILS) or "N/A"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_input = Path(tmpdir) / upload.filename
        upload.save(tmp_input)

        signed_path = signer.sign_file(
            tmp_input,
            output_dir=tmpdir,
            metadata=metadata,
            attach_original=request.form.get("attach", "true").lower() != "false",
        )

        report = {}
        if request.form.get("cloud", "true").lower() == "true":
            report = workflow.execute(
                signed_path,
                subject=request.form.get(
                    "subject", "Nuevo documento disponible para firma"
                ),
                notes=request.form.get("notes", ""),
            )

        response = send_file(
            signed_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=signed_path.name,
        )
        response.headers["X-Signing-Report"] = report and str(report)
        return response


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

