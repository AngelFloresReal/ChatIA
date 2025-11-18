# 📝 Módulo de Firma Digital y Flujo en la Nube

Este documento describe cómo habilitar la firma digital de archivos (`.pdf`, `.txt`, `.zip`)
con [IronPDF](https://ironpdf.com/python/), orquestar un flujo de subida a AWS/Google Drive y
enviar notificaciones de autorización exclusivamente para firmantes.

---

## 1. Requisitos

- Python 3.10+
- Dependencias:
  ```bash
  pip install ironpdf pythonnet boto3 google-auth google-auth-oauthlib \
             google-api-python-client google-auth-httplib2 flask
  ```
- Certificado PFX válido para firma digital y su contraseña.
- Credenciales OAuth 2.0 de Google (Drive + Gmail) configuradas en `config_oauth.py`.
- Bucket S3 (opcional) + credenciales AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).

---

## 2. Configuración

1. Edita `config_oauth.py` y completa:
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
   - `IRONPDF_CERTIFICATE_PATH`, `IRONPDF_CERTIFICATE_PASSWORD`, `IRONPDF_LICENSE_KEY`
   - `GOOGLE_DRIVE_FOLDER_ID`, `AUTHORIZED_SIGNER_EMAILS`
   - `AWS_S3_BUCKET`, `AWS_REGION` si usarás S3
2. Exporta la clave de licencia (si prefieres variables):
   ```bash
   export IRONPDF_LICENSE_KEY="xxxxxxxx"
   ```
3. Verifica que el certificado PFX sea accesible por el usuario que ejecuta los scripts.

---

## 3. Firma local con `digital_sign_service.py`

```bash
python digital_sign_service.py documento.pdf evidencias.zip notas.txt \
    --cert ./certs/firma.pfx \
    --password "SuperSecret@" \
    --out ./firmados \
    --reason "Autorización legal" \
    --location "VM AWS us-east-1" \
    --contact "legal@example.com"
```

- Para `.txt` y `.zip` el módulo genera un PDF con resumen (contenido, SHA-256, base64)
  y adjunta el archivo original dentro del PDF antes de firmar.
- Usa `--skip-attachment` si no deseas adjuntar el archivo fuente.

---

## 4. Servidor de firma para AWS / VM (`signing_server.py`)

1. Despliega una instancia (EC2, Lightsail, VM on-prem, etc.).
2. Instala dependencias y exporta variables:
   ```bash
   export SIGNER_CERT_PATH="/opt/certs/firma.pfx"
   export SIGNER_CERT_PASSWORD="SuperSecret@"
   export IRONPDF_LICENSE_KEY="xxxx"
   export AWS_ACCESS_KEY_ID=...
   export AWS_SECRET_ACCESS_KEY=...
   ```
3. Ejecuta:
   ```bash
   python signing_server.py
   ```
4. Endpoint:
   ```bash
   curl -X POST http://SERVER_IP:5000/sign \
        -F file=@contrato.pdf \
        -F reason="Firma remota" \
        -F location="AWS EC2" \
        -o contrato_firmado.pdf
   ```

> ⚙️ Opcional: coloca el servidor detrás de un túnel VPN (AWS Client VPN, OpenVPN, WireGuard)
> para exponer la API únicamente a tu red corporativa.

---

## 5. Flujo Drive + Gmail (`cloud_workflow.py`)

```python
from cloud_workflow import CloudSigningWorkflow

workflow = CloudSigningWorkflow()
report = workflow.execute(
    "./firmados/contrato_firmado.pdf",
    subject="Autorización pendiente",
    notes="Disponible solo para firma."
)
print(report)
```

Acciones:
1. Sube el PDF a S3 (si hay bucket configurado) y devuelve la URL pública/privada.
2. Sube el archivo a Google Drive dentro de `GOOGLE_DRIVE_FOLDER_ID`.
3. Concede permisos *commenter* únicamente a `AUTHORIZED_SIGNER_EMAILS`.
4. Envía un correo vía Gmail API con el enlace de Drive y nota opcional.

---

## 6. Consideraciones de seguridad

- Usa IAM Roles (EC2) o AWS Secrets Manager para las credenciales AWS.
- El certificado PFX debe almacenarse cifrado en disco (ej. AWS KMS, BitLocker, LUKS).
- Limita el acceso al servidor mediante VPN, Security Groups o Zero Trust.
- Mantén `config_oauth.py` fuera de Git (`.gitignore`) si vas a colocar credenciales reales.
- Regenera tokens OAuth periódicamente si cambias los scopes.

---

## 7. Troubleshooting

| Problema | Solución |
|----------|----------|
| `IronPdfUnavailable` | Ejecuta `pip install ironpdf pythonnet` y valida la licencia. |
| Error `ApplyDigitalSignature` | Actualiza `ironpdf` a la última versión (`pip install --upgrade ironpdf`). |
| `Missing S3 bucket` | Define `AWS_S3_BUCKET` en `config_oauth.py` o exporta la variable. |
| `Drive: insufficient permissions` | Agrega el usuario OAuth a la consola de Google Cloud (pantalla de consentimiento). |
| `Gmail send error 403` | Habilita la API Gmail y agrega el scope `https://www.googleapis.com/auth/gmail.send`. |
