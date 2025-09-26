"""
Servidor de chat con canales y autenticación por usuario/contraseña en SQLite.
Protocolo: mensajes JSON por línea.
Campos JSON usados:
 - type: "auth", "join", "msg", "system"
 - username: nombre de usuario (auth)
 - password: contraseña (auth)
 - channel: nombre del canal (join, msg)
 - from: nombre del usuario (msg)
 - text: contenido del mensaje (msg, system)
"""

import socket
import threading
import json
import traceback
import sqlite3
import sys

HOST = "0.0.0.0"
PORT = 12345
ENCODING = "utf-8"
DB_PATH = "chat.db"

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
                self.sock.sendall(s.encode(ENCODING))
        except Exception:
            self.alive = False

class ChatServer:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((host, port))
        self.sock.listen()
        self.sock.settimeout(1.0)
        self.clients_lock = threading.Lock()
        self.clients = set()
        self.channels = {}
        self.running = True
        print(f"[INIT] Servidor escuchando en {host}:{port}")

    def broadcast_all_channels_system(self, text: str):
        """Envía un mensaje de sistema a TODOS los clientes conectados,
        sin importar el canal."""
        payload = {"type": "system", "text": apply_emojis(text)}
        with self.clients_lock:
            for c in list(self.clients):
                if c.alive:
                    c.send_json(payload)

    def start(self):
        threading.Thread(target=self.admin_console, daemon=True).start()
        try:
            while self.running:
                try:
                    conn, addr = self.sock.accept()
                    if not self.running:  # Verificar si se debe cerrar después de accept()
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
                    # Socket cerrado durante shutdown
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
        
        # Cerrar todas las conexiones de clientes
        with self.clients_lock:
            for c in list(self.clients):
                try:
                    c.alive = False
                    c.sock.close()
                except:
                    pass
            self.clients.clear()
        
        # Marcar como no ejecutándose
        self.running = False
        
        # Cerrar el socket del servidor
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
        print("[ADMIN] Comandos: sys:<mensaje> | list | shutdown")
        while self.running:
            try:
                line = input()
                if not line:
                    continue
                if line.startswith("sys:"):
                    text = line[len("sys:"):].strip()
                    self.broadcast_all_channels_system(f"[ADMIN] {text}")
                    print("[ADMIN] Mensaje de sistema enviado.")
                elif line.strip() == "list":
                    with self.clients_lock:
                        print("Canales:")
                        for ch, members in self.channels.items():
                            names = [c.user for c in members if c.user]
                            print(f" - {ch}: {names}")
                elif line.strip() == "shutdown":
                    self.shutdown()
                    break  # Salir del bucle de admin_console
                else:
                    print("[ADMIN] Comando desconocido. Usa sys:, list o shutdown")
            except EOFError:
                # Ctrl+D o fin de entrada
                break
            except Exception as e:
                print(f"[ADMIN ERROR] {e}")

    def handle_client(self, client):
        """Método que maneja cada cliente (falta implementar)"""
        # Este método debería estar implementado en tu código completo
        # Por ahora solo un placeholder
        try:
            while client.alive and self.running:
                # Aquí iría la lógica de manejo del cliente
                pass
        except Exception as e:
            print(f"[CLIENT ERROR] {e}")
        finally:
            with self.clients_lock:
                self.clients.discard(client)

if __name__ == "__main__":
    server = ChatServer(HOST, PORT)
    server.start()