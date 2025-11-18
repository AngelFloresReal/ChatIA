"""
Automatizaciones para subir documentos firmados a AWS S3, Google Drive
y enviar notificaciones por correo con privilegios restringidos.
"""

from __future__ import annotations

import base64
import json
import os
from email.mime.text import MIMEText
from pathlib import Path
from typing import Iterable, Optional, Sequence

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

from config_oauth import (
    AUTHORIZED_SIGNER_EMAILS,
    AWS_REGION,
    AWS_S3_BUCKET,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_DRIVE_SCOPES,
    GOOGLE_GMAIL_SCOPES,
    OAUTH_REDIRECT_PORT,
)


class GoogleOAuthHelper:
    """Obtiene credenciales de OAuth reutilizando el flujo local."""

    def __init__(self, scopes: Sequence[str], token_file: str):
        self.scopes = scopes
        self.token_file = token_file

    def _client_config(self) -> dict:
        return {
            "installed": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": [
                    f"http://localhost:{OAUTH_REDIRECT_PORT}",
                    "http://localhost",
                    "urn:ietf:wg:oauth:2.0:oob",
                ],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

    def credentials(self) -> Credentials:
        creds: Optional[Credentials] = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(
                self.token_file, scopes=self.scopes
            )

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_config(
                self._client_config(), scopes=self.scopes
            )
            creds = flow.run_local_server(
                port=OAUTH_REDIRECT_PORT,
                prompt="consent",
                success_message="Autorización completada. Puedes cerrar esta pestaña.",
            )
            with open(self.token_file, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())

        return creds


class CloudSigningWorkflow:
    """
    Orquesta la subida a S3/Drive y el envío de correos de autorización.
    """

    def __init__(
        self,
        *,
        s3_bucket: Optional[str] = None,
        aws_region: Optional[str] = None,
        drive_folder_id: Optional[str] = None,
        signer_emails: Optional[Iterable[str]] = None,
        drive_token_file: str = "drive_token.json",
        gmail_token_file: str = "gmail_token.json",
    ):
        self.s3_bucket = s3_bucket or AWS_S3_BUCKET
        self.aws_region = aws_region or AWS_REGION
        self.drive_folder_id = drive_folder_id or GOOGLE_DRIVE_FOLDER_ID
        self.signer_emails = list(signer_emails or AUTHORIZED_SIGNER_EMAILS)
        self.drive_helper = GoogleOAuthHelper(GOOGLE_DRIVE_SCOPES, drive_token_file)
        self.gmail_helper = GoogleOAuthHelper(GOOGLE_GMAIL_SCOPES, gmail_token_file)

        self._s3_client = None

    # ------------------------------------------------------------------ #
    # AWS S3
    # ------------------------------------------------------------------ #
    @property
    def s3_client(self):
        if not self.s3_bucket:
            raise ValueError("No se configuró un bucket S3 en config_oauth.py")
        if self._s3_client is None:
            self._s3_client = boto3.client("s3", region_name=self.aws_region)
        return self._s3_client

    def upload_to_s3(self, file_path: str, *, object_name: Optional[str] = None) -> str:
        object_name = object_name or Path(file_path).name
        try:
            self.s3_client.upload_file(file_path, self.s3_bucket, object_name)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Error subiendo {file_path} a S3: {exc}") from exc

        url = f"https://{self.s3_bucket}.s3.amazonaws.com/{object_name}"
        return url

    # ------------------------------------------------------------------ #
    # Google Drive
    # ------------------------------------------------------------------ #
    def _drive_service(self):
        creds = self.drive_helper.credentials()
        return build("drive", "v3", credentials=creds)

    def upload_to_drive(self, file_path: str) -> dict:
        if not self.drive_folder_id:
            raise ValueError("Configura GOOGLE_DRIVE_FOLDER_ID en config_oauth.py")

        service = self._drive_service()
        metadata = {
            "name": Path(file_path).name,
            "parents": [self.drive_folder_id],
        }
        media = MediaFileUpload(file_path, resumable=True)
        try:
            file = (
                service.files()
                .create(body=metadata, media_body=media, fields="id, webViewLink")
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"Error subiendo archivo a Drive: {exc}") from exc

        if self.signer_emails:
            self._share_with_signers(service, file["id"])

        return file

    def _share_with_signers(self, service, file_id: str):
        for email in self.signer_emails:
            try:
                service.permissions().create(
                    fileId=file_id,
                    body={
                        "type": "user",
                        "role": "commenter",
                        "emailAddress": email,
                    },
                    sendNotificationEmail=True,
                ).execute()
            except HttpError as exc:
                raise RuntimeError(
                    f"No se pudo otorgar permisos a {email}: {exc}"
                ) from exc

    # ------------------------------------------------------------------ #
    # Gmail
    # ------------------------------------------------------------------ #
    def _gmail_service(self):
        creds = self.gmail_helper.credentials()
        return build("gmail", "v1", credentials=creds)

    def send_authorization_email(
        self,
        *,
        recipients: Optional[Iterable[str]] = None,
        subject: str,
        message_html: str,
    ) -> str:
        recipients = list(recipients or self.signer_emails)
        if not recipients:
            raise ValueError("No se proporcionaron destinatarios para la autorización.")

        mime_message = MIMEText(message_html, "html", "utf-8")
        mime_message["to"] = ", ".join(recipients)
        mime_message["subject"] = subject

        encoded_message = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()
        service = self._gmail_service()
        try:
            sent = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": encoded_message})
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"No se pudo enviar el correo: {exc}") from exc

        return sent.get("id", "")

    # ------------------------------------------------------------------ #
    # Flujo completo
    # ------------------------------------------------------------------ #
    def execute(
        self,
        file_path: str,
        *,
        subject: str = "Autorización de firma digital",
        notes: str = "",
    ) -> dict:
        """
        1. Sube el archivo a S3 (opcional).
        2. Sube a Drive con permisos restringidos.
        3. Envía correo de autorización.
        """
        report = {"s3_url": None, "drive_link": None, "email_id": None}

        if self.s3_bucket:
            report["s3_url"] = self.upload_to_s3(file_path)

        drive_file = self.upload_to_drive(file_path)
        report["drive_link"] = drive_file.get("webViewLink")

        message = self._build_email_body(report["drive_link"], notes)
        report["email_id"] = self.send_authorization_email(
            subject=subject, message_html=message
        )
        return report

    def _build_email_body(self, drive_link: str, notes: str) -> str:
        return f"""
        <p>Se ha cargado un nuevo documento para firma digital.</p>
        <p><strong>Drive:</strong> <a href="{drive_link}">{drive_link}</a></p>
        <p><strong>Notas:</strong> {notes or 'N/A'}</p>
        <p>Privilegios limitados: solo comentar/firma.</p>
        """


if __name__ == "__main__":  # pragma: no cover - utilidad manual
    import argparse

    parser = argparse.ArgumentParser(
        description="Sube documentos firmados a la nube y envía autorización."
    )
    parser.add_argument("file", help="Archivo firmado que se subirá.")
    parser.add_argument("--subject", default="Autorización de firma digital")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    workflow = CloudSigningWorkflow()
    result = workflow.execute(args.file, subject=args.subject, notes=args.notes)
    print(json.dumps(result, indent=2))

