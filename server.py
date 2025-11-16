"""
Servidor de chat con HTTPS/SSL, cifrado RSA y OAuth 2.0 de Google.
Requiere certificados SSL en el directorio 'certs/'
"""

import socket
import threading
import json
import sqlite3
import sys
import os
import ssl
import time
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

# Importar configuración
from config import (
    SERVER_HOST, SERVER_PORT, SERVER_ENCODING, DB_PATH, KEYS_DIR,
    RSA_KEY_SIZE, SOCKET_TIMEOUT, get_default_users, print_config, validate_config
)

# Importar configuración OAuth (si existe)
try:
    from config_oauth import (
        GOOGLE_CLIENT_ID, OAUTH_ENABLED, OAUTH_TOKEN_TIMEOUT
    )
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    OAUTH_AVAILABLE = True
    print("[OAUTH] ✓ Módulo OAuth 2.0 cargado")
except ImportError:
    OAUTH_AVAILABLE = False
    OAUTH_ENABLED = False
    print("[OAUTH] ⚠️  OAuth no disponible (instala: pip install google-auth google-auth-oauthlib)")

# Configuración SSL
SSL_ENABLED = True  # Cambiar a False para deshabilitar SSL
SSL_CERT_DIR = "certs"
SSL_CERTFILE = os.path.join(SSL_CERT_DIR, "server.crt")
SSL_KEYFILE = os.path.join(SSL_CERT_DIR, "server.key")

# Cache de tokens OAuth verificados
token_cache = {}

EMOJI_MAP = {
    ":)": "😊", ":(": "☹️", ":D": "😁", ":P": "😜", ";)": "😉", "B)": "😎",
    ":|": "😐", ":O": "😮", "xD": "😂", ":*": "😘", ":3": "😸", "<3": "❤️",
    ":'(": "😭", ":v": "😋", "o:)": "😇", ">:(": "😠", "T_T": "😢", "^_^": "☺️",
    "-_-": "😑", "O:)": "😇", "X_x": "😵", ":S": "😖", "B-)": "😎",
    "<(._.)>": "👽", "°-°": "😲", ":-*": "😘", "C:": "🐱"
}

def apply_emojis(text: str) -> str:
    for k, v in EMOJI_MAP.items():
        text = text.replace(k, v)
    return text

# =============================================================================
# FUNCIONES SSL
# =============================================================================

def ensure_ssl_certificates():
    """Verifica o genera certificados SSL autofirmados"""
    if not os.path.exists(SSL_CERT_DIR):
        os.makedirs(SSL_CERT_DIR)
        print(f"[SSL] 📁 Directorio de certificados creado: {SSL_CERT_DIR}/")
    
    if not os.path.exists(SSL_CERTFILE) or not os.path.exists(SSL_KEYFILE):
        print("[SSL] ⚠️  No se encontraron certificados SSL")
        print("[SSL] 🔧 Generando certificados autofirmados...")
        print("[SSL] ⚠️  IMPORTANTE: Para producción, usa certificados de una CA confiable")
        
        try:
            import subprocess
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:4096",
                "-keyout", SSL_KEYFILE,
                "-out", SSL_CERTFILE,
                "-days", "365", "-nodes",
                "-subj", "/CN=localhost/O=ChatServer/C=MX"
            ], check=True, capture_output=True)
            
            print(f"[SSL] ✓ Certificados generados exitosamente:")
            print(f"      - Certificado: {SSL_CERTFILE}")
            print(f"      - Clave: {SSL_KEYFILE}")
            return True
            
        except FileNotFoundError:
            print("[SSL] ❌ ERROR: OpenSSL no está instalado")
            print("[SSL] Instala OpenSSL o genera los certificados manualmente:")
            print(f"       openssl req -x509 -newkey rsa:4096 -keyout {SSL_KEYFILE} \\")
            print(f"               -out {SSL_CERTFILE} -days 365 -nodes \\")
            print(f"               -subj '/CN=localhost/O=ChatServer/C=MX'")
            return False
        except Exception as e:
            print(f"[SSL] ❌ ERROR generando certificados: {e}")
            return False
    else:
        print(f"[SSL] ✓ Certificados encontrados:")
        print(f"      - {SSL_CERTFILE}")
        print(f"      - {SSL_KEYFILE}")
        return True

def create_ssl_context():
    """Crea el contexto SSL para el servidor"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(SSL_CERTFILE, SSL_KEYFILE)
    
    # Configuración de seguridad
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
    
    print("[SSL] ✓ Contexto SSL configurado (TLS 1.2+)")
    return context

# =============================================================================
# FUNCIONES OAUTH 2.0
# =============================================================================

def verify_google_token(token: str) -> dict:
    """
    Verifica un token de OAuth 2.0 de Google
    Retorna información del usuario si es válido, None si no lo es
    """
    if not OAUTH_AVAILABLE:
        return None
        
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
        print(f"[OAUTH] Token inválido: {e}")
        return None
    except Exception as e:
        print(f"[OAUTH] Error verificando token: {e}")
        return None

def authenticate_oauth(username: str, token: str, email: str) -> bool:
    """
    Autentica un usuario usando OAuth 2.0
    """
    if not OAUTH_ENABLED or not OAUTH_AVAILABLE:
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
    
    print(f"[OAUTH] ✓ Usuario autenticado: {username} ({email})")
    return True

def register_oauth_user(username: str, email: str, name: str = None):
    """
    Registra automáticamente un usuario OAuth en la base de datos
    """
    try:
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
# FUNCIONES DE CRIPTOGRAFÍA RSA
# =============================================================================

def ensure_keys_directory():
    if not os.path.exists(KEYS_DIR):
        os.makedirs(KEYS_DIR)

def generate_key_pair(username: str):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=RSA_KEY_SIZE,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    ensure_keys_directory()
    private_path = os.path.join(KEYS_DIR, f"{username}_private.pem")
    public_path = os.path.join(KEYS_DIR, f"{username}_public.pem")
    
    with open(private_path, 'wb') as f:
        f.write(private_pem)
    with open(public_path, 'wb') as f:
        f.write(public_pem)
    
    return public_pem.decode('utf-8')

def load_public_key(username: str):
    public_path = os.path.join(KEYS_DIR, f"{username}_public.pem")
    if not os.path.exists(public_path):
        return None
    with open(public_path, 'rb') as f:
        public_pem = f.read()
    return serialization.load_pem_public_key(public_pem, backend=default_backend())

def load_private_key(username: str):
    private_path = os.path.join(KEYS_DIR, f"{username}_private.pem")
    if not os.path.exists(private_path):
        return None
    with open(private_path, 'rb') as f:
        private_pem = f.read()
    return serialization.load_pem_private_key(private_pem, password=None, backend=default_backend())

def encrypt_password(username: str, password: str) -> str:
    public_key = load_public_key(username)
    if not public_key:
        raise ValueError(f"No se encontró clave pública para {username}")
    
    encrypted = public_key.encrypt(
        password.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    import base64
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_password(username: str, encrypted_b64: str) -> str:
    private_key = load_private_key(username)
    if not private_key:
        raise ValueError(f"No se encontró clave privada para {username}")
    
    import base64
    encrypted = base64.b64decode(encrypted_b64.encode('utf-8'))
    decrypted = private_key.decrypt(
        encrypted,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return decrypted.decode('utf-8')

# =============================================================================
# FUNCIONES DE BASE DE DATOS
# =============================================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Crear tabla con soporte para OAuth
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_encrypted TEXT NOT NULL,
            email TEXT,
            oauth_provider TEXT
        )
    ''')
    
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        default_users = get_default_users()
        if default_users:
            for username, plain_password in default_users:
                generate_key_pair(username)
                encrypted = encrypt_password(username, plain_password)
                cursor.execute(
                    'INSERT INTO users (username, password_encrypted, email, oauth_provider) VALUES (?, ?, ?, ?)', 
                    (username, encrypted, None, None)
                )
    
    conn.commit()
    conn.close()

def authenticate_user(username: str, password: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT password_encrypted FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # Si es un usuario OAuth, no permitir autenticación tradicional
            if result[0] == 'OAUTH_USER':
                return False
            decrypted = decrypt_password(username, result[0])
            return decrypted == password
        return False
    except Exception:
        return False

def register_user(username: str, password: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return False
        
        generate_key_pair(username)
        encrypted = encrypt_password(username, password)
        cursor.execute(
            'INSERT INTO users (username, password_encrypted, email, oauth_provider) VALUES (?, ?, ?, ?)', 
            (username, encrypted, None, None)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

# =============================================================================
# CLASES DEL SERVIDOR
# =============================================================================

class ClientInfo:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.user = None
        self.channel = None
        self.lock = threading.Lock()
        self.alive = True
        self.auth_method = None  # 'password' o 'oauth'

    def send_json(self, obj: dict):
        try:
            s = json.dumps(obj, ensure_ascii=False) + "\n"
            with self.lock:
                if self.alive:
                    self.sock.sendall(s.encode(SERVER_ENCODING))
        except Exception:
            self.alive = False

class ChatServer:
    def __init__(self, host, port, use_ssl=True):
        self.use_ssl = use_ssl
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen()
        self.sock.settimeout(SOCKET_TIMEOUT)
        
        # Configurar SSL si está habilitado
        self.ssl_context = None
        if self.use_ssl:
            if ensure_ssl_certificates():
                self.ssl_context = create_ssl_context()
            else:
                print("[SSL] ⚠️  Iniciando servidor SIN SSL debido a errores")
                self.use_ssl = False
        
        self.clients_lock = threading.Lock()
        self.clients = set()
        self.channels = {}
        self.running = True
        
        protocol = "HTTPS/SSL" if self.use_ssl else "HTTP"
        auth_methods = "RSA + OAuth 2.0" if OAUTH_ENABLED else "RSA"
        print(f"[INIT] Servidor escuchando en {host}:{port} ({protocol})")
        print(f"[INIT] 🔐 Seguridad: {protocol} + {auth_methods}")

    def broadcast_to_channel(self, channel: str, obj: dict, exclude_client=None):
        if channel not in self.channels:
            return
        with self.clients_lock:
            for client in list(self.channels[channel]):
                if client.alive and client != exclude_client:
                    client.send_json(obj)

    def broadcast_all_channels_system(self, text: str):
        payload = {"type": "system", "text": apply_emojis(text)}
        with self.clients_lock:
            for c in list(self.clients):
                if c.alive:
                    c.send_json(payload)

    def remove_client_from_channel(self, client):
        if client.channel and client.channel in self.channels:
            self.channels[client.channel].discard(client)
            if not self.channels[client.channel]:
                del self.channels[client.channel]
            if client.user:
                self.broadcast_to_channel(
                    client.channel,
                    {"type": "system", "text": f"{client.user} salió del canal {client.channel}"}
                )
        client.channel = None

    def add_client_to_channel(self, client, channel):
        self.remove_client_from_channel(client)
        if channel not in self.channels:
            self.channels[channel] = set()
        self.channels[channel].add(client)
        client.channel = channel
        
        if client.user:
            self.broadcast_to_channel(
                channel,
                {"type": "system", "text": f"{client.user} se unió al canal {channel}"},
                exclude_client=client
            )
            client.send_json({"type": "system", "text": f"Te uniste al canal {channel}"})

    def start(self):
        errors = validate_config()
        if errors:
            print("❌ ERRORES EN CONFIGURACIÓN:")
            for error in errors:
                print(f"  - {error}")
            return
        
        print_config()
        init_db()
        
        threading.Thread(target=self.admin_console, daemon=True).start()
        try:
            while self.running:
                try:
                    conn, addr = self.sock.accept()
                    
                    # Envolver con SSL si está habilitado
                    if self.use_ssl and self.ssl_context:
                        try:
                            conn = self.ssl_context.wrap_socket(conn, server_side=True)
                            print(f"[SSL] ✓ Conexión SSL establecida desde {addr}")
                        except ssl.SSLError as e:
                            print(f"[SSL] ✗ Error SSL desde {addr}: {e}")
                            conn.close()
                            continue
                    
                    if not self.running:
                        conn.close()
                        break
                        
                    client = ClientInfo(conn, addr)
                    with self.clients_lock:
                        self.clients.add(client)
                    threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()
                    
                except socket.timeout:
                    continue
                except OSError as e:
                    if not self.running:
                        break
                    else:
                        print(f"[ERROR] Error en socket: {e}")
                        break
        except KeyboardInterrupt:
            print("[SHUTDOWN] Cerrando servidor por Ctrl+C")
        finally:
            self.cleanup()

    def shutdown(self):
        print("[SHUTDOWN] Avisando a todos los clientes…")
        self.broadcast_all_channels_system("[ADMIN] El servidor se cerrará ahora.")
        
        with self.clients_lock:
            for c in list(self.clients):
                try:
                    c.alive = False
                    c.sock.close()
                except:
                    pass
            self.clients.clear()
        
        self.running = False
        try:
            self.sock.close()
        except:
            pass
        print("[SHUTDOWN] Servidor cerrado.")

    def cleanup(self):
        with self.clients_lock:
            for c in list(self.clients):
                try:
                    c.sock.close()
                except:
                    pass
        try:
            self.sock.close()
        except:
            pass

    def admin_console(self):
        oauth_status = "habilitado" if OAUTH_ENABLED else "deshabilitado"
        print(f"[ADMIN] OAuth 2.0: {oauth_status}")
        print("[ADMIN] Comandos: sys:<msg> | list | shutdown | adduser:<user>:<pass>")
        while self.running:
            try:
                line = input()
                if not line:
                    continue
                    
                if line.startswith("sys:"):
                    text = line[len("sys:"):].strip()
                    self.broadcast_all_channels_system(f"[ADMIN] {text}")
                    
                elif line.startswith("adduser:"):
                    parts = line[len("adduser:"):].split(":", 1)
                    if len(parts) == 2:
                        username, password = parts[0].strip(), parts[1].strip()
                        if register_user(username, password):
                            print(f"[ADMIN] Usuario '{username}' creado")
                        else:
                            print(f"[ADMIN] Usuario '{username}' ya existe")
                            
                elif line.strip() == "list":
                    with self.clients_lock:
                        total = len([c for c in self.clients if c.alive])
                        print(f"Canales ({len(self.channels)}, {total} clientes):")
                        for ch, members in self.channels.items():
                            names = [f"{c.user}({c.auth_method or '?'})" for c in members if c.user]
                            print(f" - {ch}: {names}")
                            
                elif line.strip() == "shutdown":
                    self.shutdown()
                    break
                    
            except (EOFError, KeyboardInterrupt):
                break

    def handle_client(self, client):
        try:
            f = client.sock.makefile("r", encoding=SERVER_ENCODING)
            
            while client.alive and self.running:
                try:
                    line = f.readline()
                    if not line:
                        break
                    
                    obj = json.loads(line.strip())
                    msg_type = obj.get("type")
                    
                    # Autenticación tradicional con contraseña
                    if msg_type == "auth":
                        username = obj.get("username", "").strip()
                        password = obj.get("password", "").strip()
                        
                        if authenticate_user(username, password):
                            client.user = username
                            client.auth_method = "password"
                            client.send_json({"type": "system", "text": f"Autenticado como {username}"})
                        else:
                            client.send_json({"type": "system", "text": "Usuario o contraseña inválidos"})
                    
                    # Autenticación con OAuth 2.0
                    elif msg_type == "oauth":
                        username = obj.get("username", "").strip()
                        token = obj.get("token", "").strip()
                        email = obj.get("email", "").strip()
                        name = obj.get("name", "")
                        
                        if authenticate_oauth(username, token, email):
                            # Registrar usuario si no existe
                            register_oauth_user(username, email, name)
                            
                            client.user = username
                            client.auth_method = "oauth"
                            client.send_json({
                                "type": "system", 
                                "text": f"Autenticado como {name or username} via Google OAuth 🔐"
                            })
                        else:
                            client.send_json({
                                "type": "system", 
                                "text": "Token de OAuth inválido ❌"
                            })
                    
                    # Unirse a un canal
                    elif msg_type == "join":
                        if not client.user:
                            client.send_json({"type": "system", "text": "Debes autenticarte primero"})
                            continue
                        channel = obj.get("channel", "").strip()
                        if channel:
                            self.add_client_to_channel(client, channel)
                    
                    # Enviar mensaje
                    elif msg_type == "msg":
                        if not client.user or not client.channel:
                            continue
                        text = obj.get("text", "").strip()
                        if text:
                            message = {
                                "type": "msg",
                                "channel": client.channel,
                                "from": client.user,
                                "text": apply_emojis(text)
                            }
                            self.broadcast_to_channel(client.channel, message)
                            
                except json.JSONDecodeError:
                    continue
                except Exception:
                    break
                    
        except Exception:
            pass
        finally:
            self.remove_client_from_channel(client)
            with self.clients_lock:
                self.clients.discard(client)
            try:
                client.sock.close()
            except:
                pass
            client.alive = False

if __name__ == "__main__":
    server = ChatServer(SERVER_HOST, SERVER_PORT, use_ssl=SSL_ENABLED)
    server.start()