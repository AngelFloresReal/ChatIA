# 🔐 Integración OAuth 2.0 con Google - Guía Completa

## 📋 Índice
1. [Requisitos](#requisitos)
2. [Configuración de Google Cloud](#configuración-de-google-cloud)
3. [Instalación](#instalación)
4. [Configuración del Servidor](#configuración-del-servidor)
5. [Uso del Cliente](#uso-del-cliente)
6. [Solución de Problemas](#solución-de-problemas)

---

## 🔧 Requisitos

- Python 3.7+
- Cuenta de Google
- Proyecto en Google Cloud Console
- Dependencias Python:
  - `google-auth`
  - `google-auth-oauthlib`
  - `google-auth-httplib2`

---

## ☁️ Configuración de Google Cloud

### Paso 1: Crear Proyecto

1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. Clic en "Seleccionar proyecto" → "Nuevo proyecto"
3. Nombre: `chat-app-oauth` (o el que prefieras)
4. Clic en "Crear"

### Paso 2: Habilitar APIs

1. En el menú lateral: **APIs y servicios** → **Biblioteca**
2. Busca: `Google+ API` o `Google Identity`
3. Clic en **Habilitar**

### Paso 3: Crear Credenciales OAuth

1. En el menú lateral: **APIs y servicios** → **Credenciales**
2. Clic en **+ CREAR CREDENCIALES** → **ID de cliente de OAuth 2.0**
3. Si es la primera vez, configura la **Pantalla de consentimiento**:
   - Tipo: **Externo**
   - Nombre de la app: `Chat App`
   - Email de asistencia: tu email
   - Ámbitos: Agregar `email`, `profile`, `openid`
   - Guardar
4. Vuelve a **Credenciales** → **+ CREAR CREDENCIALES**
5. Tipo de aplicación: **Aplicación de escritorio**
6. Nombre: `Chat Desktop Client`
7. Clic en **Crear**
8. **¡IMPORTANTE!** Copia el `CLIENT_ID` y `CLIENT_SECRET`

---

## 📦 Instalación

### 1. Ejecutar Script de Setup

```bash
chmod +x setup_oauth.sh
./setup_oauth.sh
```

O manualmente:

```bash
# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install google-auth google-auth-oauthlib google-auth-httplib2
```

### 2. Crear Archivo de Configuración

Crea `config_oauth.py` con tus credenciales:

```python
GOOGLE_CLIENT_ID = "123456789-abcdefg.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-tu_secret_aqui"

GOOGLE_OAUTH_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

OAUTH_REDIRECT_PORT = 8080
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_REDIRECT_PORT}"
OAUTH_TOKEN_FILE = "oauth_token.json"
OAUTH_ENABLED = True
OAUTH_TOKEN_TIMEOUT = 3600
```

---

## 🖥️ Configuración del Servidor

### Modificar `server.py`

Agrega al inicio del archivo:

```python
from config_oauth import OAUTH_ENABLED, GOOGLE_CLIENT_ID
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import time

token_cache = {}
```

Agrega estas funciones (del archivo `server_oauth.py`):

```python
def verify_google_token(token: str) -> dict:
    # [Código de server_oauth.py]
    
def authenticate_oauth(username: str, token: str, email: str) -> bool:
    # [Código de server_oauth.py]
    
def register_oauth_user(username: str, email: str, name: str = None):
    # [Código de server_oauth.py]
```

### Modificar Tabla de Base de Datos

En la función `init_db()`, cambia la creación de tabla a:

```python
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_encrypted TEXT NOT NULL,
        email TEXT,
        oauth_provider TEXT
    )
''')
```

### Agregar Manejo de OAuth en `handle_client()`

Dentro del método `handle_client()`, agrega este caso después del caso `"auth"`:

```python
elif msg_type == "oauth":
    username = obj.get("username", "").strip()
    token = obj.get("token", "").strip()
    email = obj.get("email", "").strip()
    name = obj.get("name", "")
    
    if authenticate_oauth(username, token, email):
        register_oauth_user(username, email, name)
        client.user = username
        client.send_json({
            "type": "system", 
            "text": f"Autenticado como {name or username} via Google OAuth"
        })
    else:
        client.send_json({
            "type": "system", 
            "text": "Token de OAuth inválido"
        })
```

---

## 🚀 Uso del Cliente

### 1. Iniciar el Servidor

```bash
python server.py
```

### 2. Iniciar el Cliente OAuth

```bash
python client_oauth.py
```

### 3. Flujo de Autenticación

1. Se abrirá automáticamente tu navegador
2. Selecciona tu cuenta de Google
3. Acepta los permisos solicitados
4. El navegador mostrará: "✓ Autenticación exitosa!"
5. Vuelve a la terminal del cliente
6. Ya estarás autenticado y podrás usar el chat

### 4. Comandos Disponibles

```
/join <canal>   - Unirse a un canal
/quit           - Salir del chat
/help           - Mostrar ayuda
/whoami         - Ver tu información de Google
```

---

## 🔍 Solución de Problemas

### Error: "CLIENT_ID inválido"

- Verifica que copiaste correctamente el CLIENT_ID de Google Cloud Console
- Asegúrate de que termina en `.apps.googleusercontent.com`

### Error: "redirect_uri_mismatch"

En Google Cloud Console:
1. Ve a **Credenciales** → Tu cliente OAuth
2. En **URIs de redireccionamiento autorizados**, agrega:
   - `http://localhost:8080`
   - `http://localhost`

### Error: "Token inválido"

- El token puede haber expirado (válido por 1 hora)
- Elimina el archivo `oauth_token.json` y vuelve a autenticarte
- Verifica que el CLIENT_ID en el servidor y cliente coincidan

### El navegador no se abre

```bash
# Alternativa: Usar flujo manual
# Modifica client_oauth.py y cambia:
flow.run_local_server()
# Por:
flow.run_console()
```

### Error de instalación de dependencias

```bash
# Actualiza pip
pip install --upgrade pip

# Reinstala las dependencias
pip install --force-reinstall google-auth google-auth-oauthlib
```

---

## 🔒 Seguridad

### Consideraciones Importantes

1. **Nunca** compartas tu `CLIENT_SECRET`
2. **Nunca** subas `config_oauth.py` a Git
3. Agrega a `.gitignore`:
   ```
   config_oauth.py
   oauth_token.json
   ```
4. En producción, usa certificados SSL (HTTPS)
5. Implementa rate limiting para prevenir abusos
6. Valida tokens en cada petición crítica

### Tokens de Acceso

- Los tokens expiran después de 1 hora por defecto
- El cliente automáticamente refresca tokens expirados
- Los tokens se cachean en el servidor para eficiencia
- Elimina el caché al cerrar el servidor

---

## 📊 Diagrama de Flujo

```
Usuario → Cliente OAuth → Google OAuth Server
                ↓
         Obtener Token
                ↓
         Servidor Chat
                ↓
    Verificar Token con Google
                ↓
         Autenticación OK
                ↓
         Acceso al Chat
```

---

## 🔄 Actualización de Usuarios Existentes

Si tienes usuarios con autenticación tradicional y quieres migrar a OAuth:

```python
# Mantén ambos sistemas activos
# En server.py, el caso "auth" sigue funcionando
# Los usuarios pueden elegir cómo autenticarse

# Cliente tradicional: python client.py
# Cliente OAuth: python client_oauth.py
```

---

## 📚 Recursos Adicionales

- [Documentación OAuth 2.0 de Google](https://developers.google.com/identity/protocols/oauth2)
- [Google Auth Python Library](https://google-auth.readthedocs.io/)
- [Guía de Seguridad OAuth](https://oauth.net/2/)
- [README_SIGNATURES](README_SIGNATURES.md)

---

## ✅ Checklist de Configuración

- [ ] Proyecto creado en Google Cloud Console
- [ ] Google+ API habilitada
- [ ] Credenciales OAuth 2.0 creadas
- [ ] CLIENT_ID y CLIENT_SECRET copiados
- [ ] `config_oauth.py` creado con credenciales
- [ ] Dependencias Python instaladas
- [ ] Modificaciones en `server.py` aplicadas
- [ ] Base de datos actualizada
- [ ] Prueba de autenticación exitosa

---

## 🎉 ¡Listo!

Ahora tu aplicación de chat soporta autenticación moderna con Google OAuth 2.0, proporcionando una experiencia de usuario segura y conveniente.

Para preguntas o problemas, revisa la sección de [Solución de Problemas](#solución-de-problemas).