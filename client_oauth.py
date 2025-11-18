"""
Cliente de chat con autenticación OAuth 2.0 de Google
"""
import socket
import threading
import json
import sys
import os
import getpass
import base64
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import pickle

# Importar configuración
from config import (
    DEFAULT_CLIENT_HOST, DEFAULT_CLIENT_PORT, SERVER_ENCODING
)
from config_oauth import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_OAUTH_SCOPES,
    OAUTH_REDIRECT_PORT, OAUTH_TOKEN_FILE
)

RESET_COLOR = '\033[0m'

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

def get_google_oauth_token():
    """
    Obtiene un token de OAuth 2.0 de Google usando el flujo de autorización
    """
    creds = None
    
    # Intentar cargar credenciales guardadas
    if os.path.exists(OAUTH_TOKEN_FILE):
        try:
            with open(OAUTH_TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"⚠️  No se pudieron cargar credenciales guardadas: {e}")
    
    # Si no hay credenciales válidas, solicitar autorización
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refrescando token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"❌ Error al refrescar token: {e}")
                creds = None
        
        if not creds:
            print("\n🔐 Iniciando autenticación con Google...")
            print("=" * 50)
            
            # Crear configuración del cliente OAuth
            client_config = {
                "installed": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            
            try:
                flow = InstalledAppFlow.from_client_config(
                    client_config,
                    scopes=GOOGLE_OAUTH_SCOPES
                )
                
                # Ejecutar servidor local para recibir el código
                creds = flow.run_local_server(
                    port=OAUTH_REDIRECT_PORT,
                    prompt='consent',
                    success_message='✓ Autenticación exitosa! Puedes cerrar esta ventana.'
                )
                
                # Guardar credenciales para futuros usos
                with open(OAUTH_TOKEN_FILE, 'wb') as token:
                    pickle.dump(creds, token)
                    
            except Exception as e:
                print(f"❌ Error en autenticación OAuth: {e}")
                return None
    
    return creds

def get_user_info(creds):
    """
    Obtiene información del usuario desde Google usando el token
    """
    try:
        from google.auth.transport.requests import AuthorizedSession
        authed_session = AuthorizedSession(creds)
        
        response = authed_session.get(
            'https://www.googleapis.com/oauth2/v1/userinfo?alt=json'
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error obteniendo info de usuario: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_id_token(creds):
    """
    Extrae el ID token de las credenciales OAuth
    El ID token es lo que necesitamos para verificar identidad
    """
    try:
        # El ID token está en el campo id_token de las credenciales
        if hasattr(creds, 'id_token') and creds.id_token:
            return creds.id_token
        
        # Si no está disponible directamente, intentar obtenerlo del token_response
        if hasattr(creds, '_id_token') and creds._id_token:
            return creds._id_token
            
        # Como última opción, refrescar para obtener nuevo id_token
        print("⚠️  ID token no encontrado, refrescando...")
        creds.refresh(Request())
        
        if hasattr(creds, 'id_token') and creds.id_token:
            return creds.id_token
            
        print("❌ No se pudo obtener ID token")
        return None
        
    except Exception as e:
        print(f"❌ Error obteniendo ID token: {e}")
        return None

def recv_thread(sock, auth_flag):
    f = sock.makefile("r", encoding=SERVER_ENCODING)
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
                if "token inválido" in text_lower or "token de oauth inválido" in text_lower:
                    auth_flag["status"] = False
                elif "autenticado" in text_lower and "oauth" in text_lower:
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
    print("CHAT IA - OAuth 2.0")
    print("=" * 50)
    print("🔐 Autenticación con Google")
    print()
    
    # Obtener credenciales de OAuth
    print("Paso 1: Autenticación con Google")
    creds = get_google_oauth_token()
    
    if not creds:
        print("❌ No se pudo obtener token de OAuth")
        return
    
    # Obtener información del usuario
    user_info = get_user_info(creds)
    if not user_info:
        print("❌ No se pudo obtener información del usuario")
        return
    
    # Obtener el ID token (esto es lo importante!)
    id_token = get_id_token(creds)
    if not id_token:
        print("❌ No se pudo obtener ID token")
        print("💡 Intenta eliminar el archivo 'oauth_token.json' y vuelve a autenticarte")
        return
    
    username = user_info.get('email', '').split('@')[0]
    
    print(f"✓ Autenticado como: {user_info.get('name', username)}")
    print(f"  Email: {user_info.get('email', 'N/A')}")
    print(f"  🔑 ID Token obtenido correctamente")
    print()
    
    # Conectar al servidor
    print("Paso 2: Conectando al servidor de chat")
    host = input(f"Servidor (Enter para '{DEFAULT_CLIENT_HOST}'): ").strip() or DEFAULT_CLIENT_HOST
    port_str = input(f"Puerto (Enter para '{DEFAULT_CLIENT_PORT}'): ").strip() or str(DEFAULT_CLIENT_PORT)
    
    try:
        port = int(port_str)
    except:
        print("Puerto inválido")
        return

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print(f"✓ Conectado correctamente a {host}:{port}")
    except Exception as e:
        print(f"Error de conexión: {e}")
        return

    # Enviar autenticación con ID token (NO access token)
    auth_payload = {
        "type": "oauth",
        "username": username,
        "token": id_token,  # ← Usar ID token, no access token
        "email": user_info.get('email', ''),
        "name": user_info.get('name', username)
    }
    sock.sendall((json.dumps(auth_payload, ensure_ascii=False) + "\n").encode(SERVER_ENCODING))

    auth_flag = {"status": None}
    threading.Thread(target=recv_thread, args=(sock, auth_flag), daemon=True).start()

    print("🔄 Verificando token con el servidor...")
    
    # Timeout de 10 segundos
    import time
    timeout = 10
    start_time = time.time()
    while auth_flag["status"] is None:
        if time.time() - start_time > timeout:
            print("❌ Timeout esperando respuesta del servidor")
            return
        time.sleep(0.1)

    if not auth_flag["status"]:
        print("❌ Error de autenticación. Cerrando cliente.")
        print("💡 Intenta eliminar 'oauth_token.json' y vuelve a autenticarte")
        return

    print("✓ ¡Autenticación exitosa!")
    canal = input("Canal a unir (por ejemplo 'general') — deja vacío para unirse después: ").strip()
    current_channel = None
    if canal:
        sock.sendall((json.dumps({"type": "join", "channel": canal}, ensure_ascii=False) + "\n").encode(SERVER_ENCODING))
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
                print("  /join <canal>           - Unirse a un canal")
                print("  /quit                   - Salir del chat")
                print("  /help                   - Mostrar esta ayuda")
                print("  /whoami                 - Ver tu información")
                print("  /refresh                - Refrescar token OAuth")
                print("\n📝 Comandos de firma digital:")
                print("  /create_sign <archivo>  - Crear solicitud de firma (admin)")
                print("  /sign <token>           - Firmar documento con tu PFX")
                if current_channel:
                    print(f"  Canal actual: {current_channel}")
                print()
                continue
            
            if line.startswith("/whoami"):
                print(f"\n👤 Usuario: {username}")
                print(f"📧 Email: {user_info.get('email', 'N/A')}")
                print(f"🎭 Nombre: {user_info.get('name', 'N/A')}")
                print(f"🔐 Método: OAuth 2.0 (Google)")
                print()
                continue
            
            if line.startswith("/refresh"):
                print("\n🔄 Para refrescar token, elimina 'oauth_token.json' y reinicia el cliente")
                print()
                continue
            
            if line.startswith("/create_sign "):
                if not current_channel:
                    print("⚠️  Debes estar en un canal para crear solicitudes de firma")
                    continue
                filepath = line.split(maxsplit=1)[1].strip() if len(line.split()) > 1 else None
                if not filepath:
                    print("⚠️  Especifica la ruta del archivo: /create_sign <ruta_archivo>")
                    continue
                
                try:
                    import base64
                    with open(filepath, 'rb') as f:
                        doc_data = base64.b64encode(f.read()).decode('utf-8')
                    
                    filename = os.path.basename(filepath)
                    payload = {
                        "type": "create_sign_request",
                        "document": doc_data,
                        "filename": filename
                    }
                    sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode(SERVER_ENCODING))
                    print(f"📤 Enviando documento para crear solicitud de firma...")
                except FileNotFoundError:
                    print(f"❌ Archivo no encontrado: {filepath}")
                except Exception as e:
                    print(f"❌ Error: {e}")
                continue
            
            if line.startswith("/sign "):
                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    print("⚠️  Uso: /sign <token>")
                    print("   El servidor te pedirá tu certificado PFX y contraseña")
                    continue
                
                token = parts[1].strip()
                
                # Pedir certificado PFX
                cert_path = input("📄 Ruta a tu certificado PFX: ").strip()
                if not cert_path or not os.path.exists(cert_path):
                    print("❌ Certificado no encontrado")
                    continue
                
                # Pedir contraseña del certificado
                import getpass
                cert_password = getpass.getpass("🔐 Contraseña del certificado: ")
                if not cert_password:
                    print("❌ Se requiere contraseña del certificado")
                    continue
                
                try:
                    import base64
                    with open(cert_path, 'rb') as f:
                        cert_data = base64.b64encode(f.read()).decode('utf-8')
                    
                    payload = {
                        "type": "sign_document",
                        "token": token,
                        "certificate": cert_data,
                        "cert_password": cert_password
                    }
                    sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode(SERVER_ENCODING))
                    print("📤 Enviando certificado para firmar documento...")
                except Exception as e:
                    print(f"❌ Error: {e}")
                continue
                
            if line.startswith("/join "):
                newch = line.split(maxsplit=1)[1].strip()
                if newch:
                    sock.sendall((json.dumps({"type": "join", "channel": newch}, ensure_ascii=False) + "\n").encode(SERVER_ENCODING))
                    current_channel = newch
                    print(f"Cambiando a canal: {newch}")
                continue
                
            if not current_channel:
                print("⚠️  No estás en ningún canal. Usa /join <canal> para unirte.")
                continue
                
            payload = {"type": "msg", "channel": current_channel, "text": line}
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode(SERVER_ENCODING))
            
    except KeyboardInterrupt:
        print("\n👋 Cerrando cliente...")
        sock.close()
    except Exception as e:
        print(f"Error: {e}")
        sock.close()

if __name__ == "__main__":
    main()