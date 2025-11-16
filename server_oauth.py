"""
Modificaciones para el servidor para soportar OAuth 2.0
Agregar estas funciones al archivo server.py existente
"""

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import time

# Importar de config_oauth
from config_oauth import (
    GOOGLE_CLIENT_ID, OAUTH_ENABLED, OAUTH_TOKEN_TIMEOUT
)

# Cache de tokens verificados para evitar verificaciones repetidas
token_cache = {}

def verify_google_token(token: str) -> dict:
    """
    Verifica un token de OAuth 2.0 de Google
    Retorna información del usuario si es válido, None si no lo es
    """
    try:
        # Verificar si el token está en caché y sigue siendo válido
        if token in token_cache:
            cached_info, timestamp = token_cache[token]
            if time.time() - timestamp < OAUTH_TOKEN_TIMEOUT:
                return cached_info
            else:
                del token_cache[token]
        
        # Verificar el token con Google
        idinfo = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        # Verificar que el token sea de Google
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            return None
        
        # Guardar en caché
        token_cache[token] = (idinfo, time.time())
        
        return idinfo
        
    except ValueError as e:
        # Token inválido
        print(f"[OAUTH] Token inválido: {e}")
        return None
    except Exception as e:
        print(f"[OAUTH] Error verificando token: {e}")
        return None

def authenticate_oauth(username: str, token: str, email: str) -> bool:
    """
    Autentica un usuario usando OAuth 2.0
    """
    if not OAUTH_ENABLED:
        return False
    
    # Verificar el token con Google
    user_info = verify_google_token(token)
    
    if not user_info:
        return False
    
    # Verificar que el email coincida
    token_email = user_info.get('email', '')
    if token_email != email:
        print(f"[OAUTH] Email no coincide: {email} vs {token_email}")
        return False
    
    # Opcional: Verificar que el username coincida o crearlo automáticamente
    # Aquí puedes agregar lógica para registrar automáticamente usuarios OAuth
    
    print(f"[OAUTH] ✓ Usuario autenticado: {username} ({email})")
    return True

def register_oauth_user(username: str, email: str, name: str = None):
    """
    Registra automáticamente un usuario OAuth en la base de datos
    """
    try:
        import sqlite3
        from config import DB_PATH
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar si el usuario ya existe
        cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return True  # Usuario ya existe
        
        # Crear usuario con contraseña dummy (no se usará para OAuth)
        cursor.execute('''
            INSERT INTO users (username, password_encrypted, email, oauth_provider)
            VALUES (?, ?, ?, ?)
        ''', (username, 'OAUTH_USER', email, 'google'))
        
        conn.commit()
        conn.close()
        
        print(f"[OAUTH] ✓ Nuevo usuario OAuth registrado: {username}")
        return True
        
    except Exception as e:
        print(f"[OAUTH] Error registrando usuario: {e}")
        return False


# =============================================================================
# MODIFICACIÓN EN handle_client() del servidor
# =============================================================================
"""
Agregar este caso en el método handle_client de ChatServer:

    elif msg_type == "oauth":
        username = obj.get("username", "").strip()
        token = obj.get("token", "").strip()
        email = obj.get("email", "").strip()
        name = obj.get("name", "")
        
        if authenticate_oauth(username, token, email):
            # Registrar usuario si no existe
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
"""

# =============================================================================
# MODIFICACIÓN EN LA TABLA users (ejecutar una vez)
# =============================================================================
"""
Agregar columnas para OAuth en la base de datos:

ALTER TABLE users ADD COLUMN email TEXT;
ALTER TABLE users ADD COLUMN oauth_provider TEXT;

O modificar la función init_db() para incluir estas columnas:

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_encrypted TEXT NOT NULL,
        email TEXT,
        oauth_provider TEXT
    )
''')
"""