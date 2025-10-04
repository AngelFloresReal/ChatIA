"""
Servidor de chat con canales y cifrado simétrico de contraseñas usando Fernet.
Protocolo: mensajes JSON por línea.
NOTA: Este enfoque es educativo. Para producción se recomienda bcrypt.
"""

import socket
import threading
import json
import sqlite3
import sys
import os
from cryptography.fernet import Fernet

HOST = "0.0.0.0"
PORT = 12
ENCODING = "utf-8"
DB_PATH = "chat.db"
KEY_PATH = "secret.key"

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

def load_or_create_key():
    """Carga la clave de cifrado o crea una nueva"""
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, 'rb') as f:
            key = f.read()
        print(f"[CRYPTO] ✓ Clave de cifrado cargada desde {KEY_PATH}")
    else:
        key = Fernet.generate_key()
        with open(KEY_PATH, 'wb') as f:
            f.write(key)
        print(f"[CRYPTO] ✓ Nueva clave de cifrado generada y guardada en {KEY_PATH}")
        print(f"[CRYPTO] ⚠️  IMPORTANTE: Guarda este archivo de forma segura!")
    return key

# Inicializar el cifrador global
CIPHER_KEY = load_or_create_key()
cipher = Fernet(CIPHER_KEY)

def encrypt_password(password: str) -> str:
    """Cifra una contraseña usando Fernet"""
    encrypted = cipher.encrypt(password.encode('utf-8'))
    return encrypted.decode('utf-8')

def decrypt_password(encrypted: str) -> str:
    """Descifra una contraseña usando Fernet"""
    try:
        decrypted = cipher.decrypt(encrypted.encode('utf-8'))
        return decrypted.decode('utf-8')
    except Exception as e:
        print(f"[CRYPTO ERROR] {e}")
        return None

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
        default_users = [
            ('admin', 'admin123'),
            ('user1', 'pass1'),
            ('user2', 'pass2'),
            ('test', 'test'),
            ('alice', '1234'),
            ('beto', '4567')
        ]
        
        print("[DB] Creando usuarios con contraseñas cifradas...")
        for username, plain_password in default_users:
            encrypted = encrypt_password(plain_password)
            cursor.execute('INSERT INTO users (username, password_encrypted) VALUES (?, ?)', 
                         (username, encrypted))
            print(f"[DB]  ✓ Usuario '{username}' creado (cifrado simétrico)")
        
    conn.commit()
    conn.close()

def authenticate_user(username: str, password: str) -> bool:
    """Autentica un usuario descifrando y comparando la contraseña"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT password_encrypted FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            decrypted = decrypt_password(result[0])
            if decrypted:
                return decrypted == password
        return False
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False

def register_user(username: str, password: str) -> bool:
    """Registra un nuevo usuario en la base de datos"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return False
        
        encrypted = encrypt_password(password)
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
                    self.sock.sendall(s.encode(ENCODING))
        except Exception:
            self.alive = False

class ChatServer:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen()
        self.sock.settimeout(1.0)
        self.clients_lock = threading.Lock()
        self.clients = set()
        self.channels = {}
        self.running = True
        print(f"[INIT] Servidor escuchando en {host}:{port}")
        print(f"[INIT] 🔐 Seguridad: Cifrado simétrico con Fernet (AES-128)")

    def broadcast_to_channel(self, channel: str, obj: dict, exclude_client=None):
        """Envía un mensaje a todos los usuarios de un canal"""
        if channel not in self.channels:
            return
        
        with self.clients_lock:
            for client in list(self.channels[channel]):
                if client.alive and client != exclude_client:
                    client.send_json(obj)

    def broadcast_all_channels_system(self, text: str):
        """Envía un mensaje de sistema a TODOS los clientes conectados"""
        payload = {"type": "system", "text": apply_emojis(text)}
        with self.clients_lock:
            for c in list(self.clients):
                if c.alive:
                    c.send_json(payload)

    def remove_client_from_channel(self, client):
        """Remueve un cliente de su canal actual"""
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
        """Agrega un cliente a un canal"""
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
        """Limpieza final del servidor"""
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
        print("[ADMIN] Comandos: sys:<mensaje> | list | shutdown | adduser:<user>:<pass> | showpass:<user>")
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
                            decrypted = decrypt_password(result[0])
                            if decrypted:
                                print(f"[ADMIN] Contraseña de '{username}': {decrypted}")
                            else:
                                print(f"[ADMIN] Error al descifrar la contraseña")
                        else:
                            print(f"[ADMIN] Usuario '{username}' no encontrado")
                    except Exception as e:
                        print(f"[ADMIN ERROR] {e}")
                        
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
                    print("[ADMIN] Comandos: sys:<msg> | list | shutdown | adduser:<user>:<pass> | showpass:<user>")
                    
            except EOFError:
                break
            except Exception as e:
                print(f"[ADMIN ERROR] {e}")

    def handle_client(self, client):
        """Maneja la comunicación con un cliente específico"""
        print(f"[CONN] Cliente conectado desde {client.addr}")
        
        try:
            f = client.sock.makefile("r", encoding=ENCODING)
            
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
                            print(f"[AUTH] ✓ Usuario {username} autenticado desde {client.addr}")
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
    server = ChatServer(HOST, PORT)
    server.start()