"""
Configuración para OAuth 2.0 de Google
"""

import os

# ============================================
# CONFIGURACIÓN OAUTH 2.0
# ============================================

# Credenciales de Google Cloud Console
GOOGLE_CLIENT_ID = ''
GOOGLE_CLIENT_SECRET = ''

# Scopes necesarios para obtener información del usuario
# IMPORTANTE: 'openid' debe estar primero para obtener el ID token
GOOGLE_OAUTH_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

# Scopes adicionales para automatizaciones (Drive / Gmail)
GOOGLE_DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

GOOGLE_GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.send'
]

# Puerto para el servidor de redirección local
OAUTH_REDIRECT_PORT = 8080
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_REDIRECT_PORT}"

# Archivo para guardar credenciales (opcional, para sesiones persistentes)
OAUTH_TOKEN_FILE = "oauth_token.json"
DRIVE_TOKEN_FILE = "drive_token.json"
GMAIL_TOKEN_FILE = "gmail_token.json"

# El servidor debe aceptar tokens de OAuth en lugar de contraseñas
OAUTH_ENABLED = True  # Cambiar a False para usar autenticación tradicional

# Timeout para verificación de tokens (segundos)
OAUTH_TOKEN_TIMEOUT = 3600  # 1 hora

# Configuración para automatizaciones adicionales
GOOGLE_DRIVE_FOLDER_ID = ''  # Carpeta destino para documentación firmada
AUTHORIZED_SIGNER_EMAILS = []  # Lista de emails que podrán firmar

# Opcional: ruta al certificado PFX y contraseña usados por IronPDF
IRONPDF_CERTIFICATE_PATH = ''
IRONPDF_CERTIFICATE_PASSWORD = ''
IRONPDF_LICENSE_KEY = ''

# Configuración AWS para el módulo de firma en servidores remotos
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET', '')

