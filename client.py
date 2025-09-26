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
import os

ENCODING = "utf-8"
RESET_COLOR = '\033[0m'

# Detectar si el terminal soporta colores
def supports_color():
    """Detecta si el terminal soporta colores ANSI"""
    return (
        hasattr(sys.stderr, "isatty") and sys.stderr.isatty() and
        os.environ.get('TERM') != 'dumb'
    ) or os.environ.get('FORCE_COLOR') == '1'

def colorize_text(text, color_code):
    """Aplica color al texto si el terminal lo soporta"""
    if supports_color() and color_code:
        return f"{color_code}{text}{RESET_COLOR}"
    return text

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
            color = obj.get("color", "")
            
            if t == "system":
                text = obj.get('text', '')
                if color:
                    print(f"[SYSTEM] {colorize_text(text, color)}")
                else:
                    print(f"[SYSTEM] {text}")
                    
                text_lower = text.lower()
                if "usuario o contraseña inválidos" in text_lower:
                    auth_flag["status"] = False
                elif "autenticado como" in text_lower:
                    auth_flag["status"] = True
                    
            elif t == "msg":
                ch = obj.get("channel")
                frm = obj.get("from")
                text = obj.get("text")
                
                if color:
                    colored_from = colorize_text(frm, color)
                    print(f"[{ch}] {colored_from}: {text}")
                else:
                    print(f"[{ch}] {frm}: {text}")
                    
            else:
                print("[RAW]", obj)
                
    except Exception as e:
        print("[ERROR recv]", e)
    finally:
        sock.close()

def main():
    print("CHAT IA")
    print("=" * 30)
    
    host = input("Servidor (por defecto localhost): ").strip() or "localhost"
    port_str = input("Puerto (por defecto 12345): ").strip() or "12345"
    try:
        port = int(port_str)
    except:
        print("Puerto inválido")
        return

    print("\n Inicio de sesión")
    username = input("Usuario: ").strip()
    password = input("Contraseña: ").strip()
    if not username or not password:
        print("¡Usuario y contraseña requeridos!")
        return

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print(f"Conectado correctamente a {host}:{port}")
    except Exception as e:
        print(f"Error de conexión: {e}")
        return

    auth_payload = {
        "type": "auth",
        "username": username,
        "password": password
    }
    sock.sendall((json.dumps(auth_payload, ensure_ascii=False) + "\n").encode(ENCODING))

    auth_flag = {"status": None}
    threading.Thread(target=recv_thread, args=(sock, auth_flag), daemon=True).start()

    # Esperar hasta saber si la auth fue exitosa o no
    print("Autenticando...")
    print("...")
    while auth_flag["status"] is None:
        pass

    if not auth_flag["status"]:
        print("Error de autenticación. Cerrando cliente.")
        return

    print("¡Autenticación exitosa!")
    canal = input("Canal a unir (por ejemplo 'general') — deja vacío para unirse después: ").strip()
    current_channel = None
    if canal:
        sock.sendall((json.dumps({"type": "join", "channel": canal}, ensure_ascii=False) + "\n").encode(ENCODING))
        current_channel = canal

    print("\n💬 Chat iniciado!")
    print("Comandos: /join <canal>, /quit, /help")
    print("=" * 50)
    
    try:
        while True:
            line = input()
            if not line:
                continue
                
            if line.startswith("/quit"):
                print("👋 Saliendo...")
                sock.close()
                break
                
            if line.startswith("/help"):
                print("\n📋 Comandos disponibles:")
                print("  /join <canal>  - Unirse a un canal")
                print("  /quit          - Salir del chat")
                print("  /help          - Mostrar esta ayuda")
                print("  /colors        - Probar colores")
                if current_channel:
                    print(f"  Canal actual: {current_channel}")
                print()
                continue
                
            if line.startswith("/colors"):
                print("\n🌈 Prueba de colores:")
                test_colors = [
                    '\033[91m', '\033[92m', '\033[93m', '\033[94m', 
                    '\033[95m', '\033[96m', '\033[97m'
                ]
                for i, color in enumerate(test_colors):
                    print(f"{colorize_text(f'Color {i+1}', color)}")
                print()
                continue
                
            if line.startswith("/join "):
                newch = line.split(maxsplit=1)[1].strip()
                if newch:
                    sock.sendall((json.dumps({"type": "join", "channel": newch}, ensure_ascii=False) + "\n").encode(ENCODING))
                    current_channel = newch
                    print(f"🔄 Cambiando a canal: {newch}")
                continue
                
            if not current_channel:
                print("⚠️  No estás en ningún canal. Usa /join <canal> para unirte.")
                continue
                
            payload = {"type": "msg", "channel": current_channel, "text": line}
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode(ENCODING))
            
    except KeyboardInterrupt:
        print("\n👋 Cerrando cliente...")
        sock.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        sock.close()

if __name__ == "__main__":
    main()