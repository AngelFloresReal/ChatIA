"""
Cliente de consola.
Protocolo JSON por línea (mismo formato que el servidor).
Uso:
 - al iniciar pide host, puerto, usuario, contraseña y canal
 - comandos:
    /join <canal>   -> cambiar de canal
    /quit           -> salir
"""
import socket
import threading
import json
import sys

ENCODING = "utf-8"

def recv_thread(sock, auth_flag):
    f = sock.makefile("r", encoding=ENCODING)
    try:
        while True:
            line = f.readline()
            if not line:
                print("[INFO] Conexión cerrada por el servidor.")
                if auth_flag["status"] is None:
                    auth_flag["status"] = False
                break
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get("type")
            if t == "system":
                print(f"[SYSTEM] {obj.get('text')}")
                text = obj.get("text", "").lower()
                if "usuario o contraseña inválidos" in text:
                    auth_flag["status"] = False
                elif "autenticado como" in text:
                    auth_flag["status"] = True
            elif t == "msg":
                ch = obj.get("channel")
                frm = obj.get("from")
                text = obj.get("text")
                print(f"[{ch}] {frm}: {text}")
            else:
                print("[RAW]", obj)
    except Exception as e:
        print("[ERROR recv]", e)
    finally:
        sock.close()

def main():
    host = input("Servidor (por defecto localhost): ").strip() or "localhost"
    port_str = input("Puerto (por defecto 12345): ").strip() or "12345"
    try:
        port = int(port_str)
    except:
        print("Puerto inválido")
        return

    username = input("Usuario: ").strip()
    password = input("Contraseña: ").strip()
    if not username or not password:
        print("Usuario y contraseña requeridos")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    auth_payload = {
        "type": "auth",
        "username": username,
        "password": password
    }
    sock.sendall((json.dumps(auth_payload, ensure_ascii=False) + "\n").encode(ENCODING))

    auth_flag = {"status": None}
    threading.Thread(target=recv_thread, args=(sock, auth_flag), daemon=True).start()

    # Esperar hasta saber si la auth fue exitosa o no
    while auth_flag["status"] is None:
        pass

    if not auth_flag["status"]:
        print("Error de autenticación. Cerrando cliente.")
        return

    canal = input("Canal a unir (por ejemplo general) — deja vacío para unirse después: ").strip()
    current_channel = None
    if canal:
        sock.sendall((json.dumps({"type": "join", "channel": canal}, ensure_ascii=False) + "\n").encode(ENCODING))
        current_channel = canal

    print("Escribe mensajes. Comandos: /join <canal>, /quit")
    try:
        while True:
            line = input()
            if not line:
                continue
            if line.startswith("/quit"):
                print("Saliendo...")
                sock.close()
                break
            if line.startswith("/join "):
                newch = line.split(maxsplit=1)[1].strip()
                if newch:
                    sock.sendall((json.dumps({"type": "join", "channel": newch}, ensure_ascii=False) + "\n").encode(ENCODING))
                    current_channel = newch
                continue
            if not current_channel:
                print("No estás en ningún canal. Usa /join <canal> para unirte.")
                continue
            payload = {"type": "msg", "channel": current_channel, "text": line}
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode(ENCODING))
    except KeyboardInterrupt:
        print("Cerrando cliente")
        sock.close()
    except Exception as e:
        print("Error:", e)
        sock.close()

if __name__ == "__main__":
    main()
