#!/usr/bin/env python3
"""
Servidor de chat con canales y autenticación por clave.
Protocolo: mensajes JSON por línea.
Campos JSON usados:
 - type: "auth", "join", "msg", "system"
 - key: clave de autenticación (auth)
 - channel: nombre del canal (join, msg)
 - from: nombre del usuario (msg)
 - text: contenido del mensaje (msg, system)
"""

import socket
import threading
import json
import traceback

HOST = "0.0.0.0"
PORT = 12345
ENCODING = "utf-8"

# Mapas de claves válidas: key -> username (en un sistema real, sería DB)
VALID_KEYS = {
    "clave_alice_123": "alice",
    "clave_beto_456": "beto",
    "secret_admin_999": "admin"
}

EMOJI_MAP = {
    ":)": "😊",     # Sonrisa
    ":(": "☹️",     # Tristeza
    ":D": "😁",     # Sonrisa amplia
    ":P": "😜",     # Lengua afuera
    ";)": "😉",     # Guiño
    "B)": "😎",     # Gafas de sol
    ":|": "😐",     # Neutral
    ":O": "😮",     # Sorprendido
    "xD": "😂",     # Risa
    ":*": "😘",     # Beso
    ":3": "😸",     # Carita de gato
    "<3": "❤️",     # Corazón
    ":'(": "😭",     # Llorando
    ":v": "😋",     # Carita traviesa
    "o:)": "😇",    # Ángel
    ">:(": "😠",     # Enfado
    "T_T": "😢",     # Llorando fuerte
    "^_^": "☺️",     # Sonrisa tierna
    "-_-": "😑",     # Desinterés
    "O:)": "😇",     # Ángel (alternativa)
    "X_x": "😵",     # Desmayado
    ":S": "😖",     # Confusión
    "B-)": "😎",     # Gafas de sol con estilo
    "<(._.)>": "👽", # Carita alienígena
    "°-°": "😲",     # Sorprendido
    ":-*": "😘",     # Beso (alternativo)
    "C:": "🐱",      # Carita gato (alternativa)
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
        self.clients_lock = threading.Lock()
        self.clients = set()  # set of ClientInfo
        self.channels = {}  # channel -> set(ClientInfo)
        print(f"[INIT] Servidor escuchando en {host}:{port}")

    def start(self):
        threading.Thread(target=self.admin_console, daemon=True).start()
        try:
            while True:
                conn, addr = self.sock.accept()
                client = ClientInfo(conn, addr)
                with self.clients_lock:
                    self.clients.add(client)
                threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()
        except KeyboardInterrupt:
            print("[SHUTDOWN] Cerrando servidor")
            self.sock.close()

    def handle_client(self, client: ClientInfo):
        f = client.sock.makefile("r", encoding=ENCODING)
        try:
            # First we expect auth message quickly
            line = f.readline()
            if not line:
                return
            obj = json.loads(line)
            if obj.get("type") != "auth" or "key" not in obj:
                client.send_json({"type": "system", "text": "Protocolo: primero manda auth con key"})
                client.sock.close()
                return

            key = obj["key"]
            if key not in VALID_KEYS:
                # veto automático
                client.send_json({"type": "system", "text": "Clave inválida. Conexión cerrada."})
                client.sock.close()
                return

            client.user = VALID_KEYS[key]
            client.send_json({"type": "system", "text": f"Autenticado como {client.user}. Usa 'join' para entrar a un canal."})
            print(f"[CONNECT] {client.addr} autenticado como {client.user}")

            # read loop
            while True:
                line = f.readline()
                if not line:
                    break
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                t = obj.get("type")
                if t == "join":
                    channel = obj.get("channel")
                    if not channel:
                        client.send_json({"type":"system","text":"join requiere 'channel'"})
                        continue
                    self.join_channel(client, channel)
                elif t == "msg":
                    channel = obj.get("channel")
                    text = obj.get("text","")
                    if client.channel != channel:
                        client.send_json({"type":"system","text":"No estás en ese canal. Haz join primero."})
                        continue
                    text = apply_emojis(text)
                    self.broadcast_channel(channel, {
                        "type":"msg",
                        "channel": channel,
                        "from": client.user,
                        "text": text
                    })
                else:
                    client.send_json({"type":"system","text":"Tipo de mensaje desconocido."})

        except Exception as e:
            print("[ERROR] en handle_client:", e)
            traceback.print_exc()
        finally:
            self.disconnect_client(client)

    def join_channel(self, client: ClientInfo, channel: str):
        with self.clients_lock:
            # remove from old channel
            if client.channel:
                old = self.channels.get(client.channel, set())
                old.discard(client)
            # add to new
            client.channel = channel
            self.channels.setdefault(channel, set()).add(client)

        client.send_json({"type":"system","text":f"Has entrado al canal '{channel}'"})
        # notify only that channel
        self.broadcast_channel(channel, {"type":"system","text":f"{client.user} se ha unido al canal {channel}"}, exclude=client)

    def broadcast_channel(self, channel: str, obj: dict, exclude: ClientInfo = None):
        # send only to clients that are in this channel
        with self.clients_lock:
            members = set(self.channels.get(channel, set()))
        for c in members:
            if c is exclude or not c.alive:
                continue
            c.send_json(obj)

    def broadcast_all_channels_system(self, text: str):
        # Mensajes de sistema que deben llegar a TODOS los canales
        payload = {"type":"system","text": apply_emojis(text)}
        with self.clients_lock:
            for c in list(self.clients):
                if c.alive:
                    c.send_json(payload)

    def disconnect_client(self, client: ClientInfo):
        try:
            client.alive = False
            client.sock.close()
        except Exception:
            pass
        with self.clients_lock:
            self.clients.discard(client)
            if client.channel and self.channels.get(client.channel):
                self.channels[client.channel].discard(client)
        print(f"[DISCONNECT] {client.addr} - {client.user}")

    def admin_console(self):
        # Permite enviar mensajes de sistema a todos los canales
        print("[ADMIN] Escribe: sys:mensaje  => para mandar mensaje de sistema a todos los canales")
        print("[ADMIN] list => ver canales y usuarios")
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not line:
                continue
            if line.startswith("sys:"):
                text = line[len("sys:"):].strip()
                self.broadcast_all_channels_system(f"[SYSTEM] {text}")
                print("[ADMIN] Mensaje de sistema enviado.")
            elif line.strip() == "list":
                with self.clients_lock:
                    print("Canales:")
                    for ch, members in self.channels.items():
                        names = [c.user for c in members if c.user]
                        print(f" - {ch}: {names}")
            else:
                print("[ADMIN] Comando desconocido. Usa sys: o list")

if __name__ == "__main__":
    server = ChatServer(HOST, PORT)
    server.start()
