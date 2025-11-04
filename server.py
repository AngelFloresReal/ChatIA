"""
Servidor de chat con canales y cifrado ASIMÉTRICO de contraseñas usando RSA.
Protocolo: mensajes JSON por línea.
NOTA EDUCATIVA: Este es un ejemplo de cifrado asimétrico.
Cada usuario tiene su propio par de claves (pública/privada).
"""

import socket
import threading
import json
import sqlite3
import sys
import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

# Importar configuración
from config import (
    SERVER_HOST, SERVER_PORT, SERVER_ENCODING, DB_PATH, KEYS_DIR,
    RSA_KEY_SIZE, SOCKET_TIMEOUT, get_default_users, print_config, validate_config
)

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

def ensure_keys_directory():
    """Asegura que exista el directorio para las claves"""
    if not os.path.exists(KEYS_DIR):
        os.makedirs(KEYS_DIR)
        print(f"[CRYPTO] ✓ Directorio de claves creado: {KEYS_DIR}/")

def generate_key_pair(username: str):
    """Genera un par de claves RSA (pública/privada) para un usuario"""
    # Generar clave privada
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=RSA_KEY_SIZE,
        backend=default_backend()
    )
    
    # Derivar clave pública de la privada
    public_key = private_key.public_key()
    
    # Serializar clave privada
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serializar clave pública
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Guardar las claves en archivos
    ensure_keys_directory()
    
    private_path = os.path.join(KEYS_DIR, f"{username}_private.pem")
    public_path = os.path.join(KEYS_DIR, f"{username}_public.pem")
    
    with open(private_path, 'wb') as f:
        f.write(private_pem)
    
    with open(public_path, 'wb') as f:
        f.write(public_pem)
    
    print(f"[CRYPTO] ✓ Par de claves generado para '{username}' ({RSA_KEY_SIZE} bits)")
    print(f"         - Privada: {private_path}")
    print(f"         - Pública: {public_path}")
    
    return public_pem.decode('utf-8')

def load_public_key(username: str):
    """Carga la clave pública de un usuario"""
    public_path = os.path.join(KEYS_DIR, f"{username}_public.pem")
    
    if not os.path.exists(public_path):
        return None
    
    with open(public_path, 'rb') as f:
        public_pem = f.read()
    
    public_key = serialization.load_pem_public_key(
        public_pem,
        backend=default_backend()
    )
    
    return public_key

def load_private_key(username: str):
    """Carga la clave privada de un usuario"""
    private_path = os.path.join(KEYS_DIR, f"{username}_private.pem")
    
    if not os.path.exists(private_path):
        return None
    
    with open(private_path, 'rb') as f:
        private_pem = f.read()
    
    private_key = serialization.load_pem_private_key(
        private_pem,
        password=None,
        backend=default_backend()
    )
    
    return private_key

def encrypt_password(username: str, password: str) -> str:
    """Cifra una contraseña usando la clave PÚBLICA del usuario"""
    public_key = load_public_key(username)
    
    if not public_key:
        raise ValueError(f"No se encontró clave pública para {username}")
    
    # Cifrar con clave pública
    encrypted = public_key.encrypt(
        password.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    # Convertir bytes a string base64 para almacenar en DB
    import base64
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_password(username: str, encrypted_b64: str) -> str:
    """Descifra una contraseña usando la clave PRIVADA del usuario"""
    private_key = load_private_key(username)
    
    if not private_key:
        raise ValueError(f"No se encontró clave privada para {username}")
    
    # Decodificar de base64
    import base64
    encrypted = base64.b64decode(encrypted_b64.encode('utf-8'))
    
    # Descifrar con clave privada
    decrypted = private_key.decrypt(
        encrypted,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    return decrypted.decode('utf-8')

def init_db():
    """Inicializa la base de datos con usuarios por defecto si no existe"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_encrypted TEXT NOT NULL
        )
    ''')
    
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        default_users = get_default_users()
        
        if default_users:
            print(f"[DB] Creando {len(default_users)} usuarios con cifrado ASIMÉTRICO (RSA-{RSA_KEY_SIZE})...")
            print("="*60)
            for username, plain_password in default_users:
                # Generar par de claves para cada usuario
                generate_key_pair(username)
                
                # Cifrar contraseña con clave PÚBLICA
                encrypted = encrypt_password(username, plain_password)
                
                cursor.execute('INSERT INTO users (username, password_encrypted) VALUES (?, ?)', 
                             (username, encrypted))
                print(f"[DB]  ✓ Usuario '{username}' creado con RSA")
            
            print("="*60)
        else:
            print("[DB] No se crearán usuarios por defecto (configuración deshabilitada)")
        
    conn.commit()
    conn.close()

def authenticate_user(username: str, password: str) -> bool:
    """Autentica un usuario descifrando con su clave PRIVADA"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT password_encrypted FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # Descifrar con clave PRIVADA
            decrypted = decrypt_password(username, result[0])
            return decrypted == password
        return False
    except Exception as e:
        print(f"[AUTH ERROR] {e}")
        return False

def register_user(username: str, password: str) -> bool:
    """Registra un nuevo usuario con su par de claves RSA"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return False
        
        # Generar par de claves
        generate_key_pair(username)
        
        # Cifrar con clave pública
        encrypted = encrypt_password(username, password)
        
        cursor.execute('INSERT INTO users (username, password_encrypted) VALUES (?, ?)', 
                      (username, encrypted))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False

class ClientInfo:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.user = None
        self.channel = None
        self.lock = threading.Lock()
        self.alive = True

    def send_json(self, obj: dict):
        try:
            s = json.dumps(obj, ensure_ascii=False) + "\n"
            with self.lock:
                if self.alive:
                    self.sock.sendall(s.encode(SERVER_ENCODING))
        except Exception:
            self.alive = False

class ChatServer:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen()
        self.sock.settimeout(SOCKET_TIMEOUT)
        self.clients_lock = threading.Lock()
        self.clients = set()
        self.channels = {}
        self.running = True
        print(f"[INIT] Servidor escuchando en {host}:{port}")
        print(f"[INIT] 🔐 Seguridad: Cifrado ASIMÉTRICO con RSA-{RSA_KEY_SIZE}")

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
        # Validar configuración
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
                    if not self.running:
                        conn.close()
                        break
                    client = ClientInfo(conn, addr)
                    with self.clients_lock:
                        self.clients.add(client)
                    threading.Thread(target=self.handle_client,
                                   args=(client,), daemon=True).start()
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
        print("[ADMIN] Comandos: sys:<msg> | list | shutdown | adduser:<user>:<pass> | showpass:<user> | showkeys:<user>")
        while self.running:
            try:
                line = input()
                if not line:
                    continue
                    
                if line.startswith("sys:"):
                    text = line[len("sys:"):].strip()
                    self.broadcast_all_channels_system(f"[ADMIN] {text}")
                    print("[ADMIN] Mensaje de sistema enviado.")
                    
                elif line.startswith("adduser:"):
                    parts = line[len("adduser:"):].split(":", 1)
                    if len(parts) == 2:
                        username, password = parts[0].strip(), parts[1].strip()
                        if register_user(username, password):
                            print(f"[ADMIN] Usuario '{username}' creado exitosamente")
                        else:
                            print(f"[ADMIN] Error: el usuario '{username}' ya existe")
                    else:
                        print("[ADMIN] Formato: adduser:<usuario>:<contraseña>")
                
                elif line.startswith("showpass:"):
                    username = line[len("showpass:"):].strip()
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('SELECT password_encrypted FROM users WHERE username = ?', (username,))
                        result = cursor.fetchone()
                        conn.close()
                        
                        if result:
                            decrypted = decrypt_password(username, result[0])
                            print(f"[ADMIN] Contraseña de '{username}': {decrypted}")
                        else:
                            print(f"[ADMIN] Usuario '{username}' no encontrado")
                    except Exception as e:
                        print(f"[ADMIN ERROR] {e}")
                
                elif line.startswith("showkeys:"):
                    username = line[len("showkeys:"):].strip()
                    private_path = os.path.join(KEYS_DIR, f"{username}_private.pem")
                    public_path = os.path.join(KEYS_DIR, f"{username}_public.pem")
                    
                    if os.path.exists(private_path) and os.path.exists(public_path):
                        print(f"[ADMIN] Claves de '{username}':")
                        print(f"  - Privada: {private_path}")
                        print(f"  - Pública: {public_path}")
                    else:
                        print(f"[ADMIN] No se encontraron claves para '{username}'")
                        
                elif line.strip() == "list":
                    with self.clients_lock:
                        total_clients = len([c for c in self.clients if c.alive])
                        if not self.channels:
                            print(f"No hay canales aún. ({total_clients} clientes conectados)")
                        else:
                            print(f"Canales ({len(self.channels)} canales, {total_clients} clientes conectados):")
                            for ch, members in self.channels.items():
                                names = [c.user for c in members if c.user]
                                print(f" - {ch}: {names} ({len(names)} usuarios)")
                                
                elif line.strip() == "shutdown":
                    self.shutdown()
                    break
                    
                else:
                    print("[ADMIN] Comandos: sys:<msg> | list | shutdown | adduser:<user>:<pass> | showpass:<user> | showkeys:<user>")
                    
            except EOFError:
                break
            except Exception as e:
                print(f"[ADMIN ERROR] {e}")

    def handle_client(self, client):
        print(f"[CONN] Cliente conectado desde {client.addr}")
        
        try:
            f = client.sock.makefile("r", encoding=SERVER_ENCODING)
            
            while client.alive and self.running:
                try:
                    line = f.readline()
                    if not line:
                        break
                    
                    try:
                        obj = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue
                    
                    msg_type = obj.get("type")
                    
                    if msg_type == "auth":
                        username = obj.get("username", "").strip()
                        password = obj.get("password", "").strip()
                        
                        if not username or not password:
                            client.send_json({"type": "system", "text": "Usuario y contraseña requeridos"})
                            continue
                        
                        if authenticate_user(username, password):
                            client.user = username
                            client.send_json({"type": "system", "text": f"Autenticado como {username}"})
                            print(f"[AUTH] ✓ Usuario {username} autenticado (RSA) desde {client.addr}")
                        else:
                            client.send_json({"type": "system", "text": "Usuario o contraseña inválidos"})
                            print(f"[AUTH] ✗ Intento fallido para {username} desde {client.addr}")
                    
                    elif msg_type == "join":
                        if not client.user:
                            client.send_json({"type": "system", "text": "Debes autenticarte primero"})
                            continue
                        
                        channel = obj.get("channel", "").strip()
                        if not channel:
                            client.send_json({"type": "system", "text": "Nombre de canal requerido"})
                            continue
                        
                        self.add_client_to_channel(client, channel)
                        print(f"[JOIN] {client.user} se unió al canal {channel}")
                    
                    elif msg_type == "msg":
                        if not client.user:
                            client.send_json({"type": "system", "text": "Debes autenticarte primero"})
                            continue
                        
                        if not client.channel:
                            client.send_json({"type": "system", "text": "Debes unirte a un canal primero"})
                            continue
                        
                        channel = obj.get("channel", "").strip()
                        text = obj.get("text", "").strip()
                        
                        if not text:
                            continue
                        
                        if channel != client.channel:
                            client.send_json({"type": "system", "text": f"No estás en el canal {channel}"})
                            continue
                        
                        processed_text = apply_emojis(text)
                        message = {
                            "type": "msg",
                            "channel": channel,
                            "from": client.user,
                            "text": processed_text
                        }
                        
                        self.broadcast_to_channel(channel, message)
                        print(f"[MSG] [{channel}] {client.user}: {text}")
                    
                    else:
                        client.send_json({"type": "system", "text": f"Tipo de mensaje desconocido: {msg_type}"})
                
                except Exception as e:
                    print(f"[CLIENT ERROR] Error procesando mensaje de {client.addr}: {e}")
                    break
                    
        except Exception as e:
            print(f"[CLIENT ERROR] Error en handle_client para {client.addr}: {e}")
        finally:
            print(f"[DISC] Cliente {client.addr} desconectado")
            if client.user:
                print(f"[DISC] Usuario {client.user} desconectado")
            
            self.remove_client_from_channel(client)
            
            with self.clients_lock:
                self.clients.discard(client)
            
            try:
                client.sock.close()
            except:
                pass
            
            client.alive = False

if __name__ == "__main__":
    server = ChatServer(SERVER_HOST, SERVER_PORT)
    server.start()