#!/usr/bin/env python3
"""
Cliente de consola.
Protocolo JSON por línea (mismo formato que el servidor).
Uso:
 - al iniciar pide host, puerto, clave (key) y canal
 - entrada en consola: escribe el mensaje y presiona Enter para enviarlo al canal seleccionado
 - comandos cliente:
    /join <canal>   -> cambiar de canal
    /quit           -> salir
"""

import socket
import threading
import json
import sys

ENCODING = "utf-8"

def recv_thread(sock):
    f = sock.makefile("r", encoding=ENCODING)
    try:
        while True:
            line = f.readline()
            if not line:
                print("[INFO] Conexión cerrada por el servidor.")
                break
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get("type")
            if t == "system":
                print(f"[SYSTEM] {obj.get('text')}")
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

    key = input("Introduce tu clave de acceso: ").strip()
    if not key:
        print("Clave requerida")
        return

    # Conectar
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    # enviar auth
    sock.sendall((json.dumps({"type":"auth","key": key}, ensure_ascii=False) + "\n").encode(ENCODING))

    # start receiving thread
    threading.Thread(target=recv_thread, args=(sock,), daemon=True).start()

    # join canal inicial (opcional)
    canal = input("Canal a unir (por ejemplo general) — deja vacío para unirse después: ").strip()
    if canal:
        sock.sendall((json.dumps({"type":"join","channel": canal}, ensure_ascii=False) + "\n").encode(ENCODING))
        current_channel = canal
    else:
        current_channel = None

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
                    sock.sendall((json.dumps({"type":"join","channel": newch}, ensure_ascii=False) + "\n").encode(ENCODING))
                    current_channel = newch
                continue
            # enviar mensaje al canal actual
            if not current_channel:
                print("No estás en ningún canal. Usa /join <canal> para unirte.")
                continue
            payload = {"type":"msg","channel": current_channel, "text": line}
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode(ENCODING))
    except KeyboardInterrupt:
        print("Cerrando cliente")
        sock.close()
    except Exception as e:
        print("Error:", e)
        sock.close()

if __name__ == "__main__":
    main()
