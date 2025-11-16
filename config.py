"""
Configuración centralizada del proyecto usando variables de entorno
"""
import os
from pathlib import Path

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent.absolute()

# ============================================
# CONFIGURACIÓN DEL SERVIDOR
# ============================================
SERVER_HOST = os.getenv('CHAT_SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.getenv('CHAT_SERVER_PORT', '12345'))
SERVER_ENCODING = os.getenv('CHAT_ENCODING', 'utf-8')

# ============================================
# CONFIGURACIÓN DE BASE DE DATOS
# ============================================
DB_PATH = os.getenv('CHAT_DB_PATH', str(BASE_DIR / 'chat.db'))

# ============================================
# CONFIGURACIÓN DE CRIPTOGRAFÍA
# ============================================
KEYS_DIR = os.getenv('CHAT_KEYS_DIR', str(BASE_DIR / 'user_keys'))
RSA_KEY_SIZE = int(os.getenv('CHAT_RSA_KEY_SIZE', '2048'))

# ============================================
# CONFIGURACIÓN DE LOGS
# ============================================
LOG_LEVEL = os.getenv('CHAT_LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('CHAT_LOG_FILE', str(BASE_DIR / 'chat.log'))

# ============================================
# CONFIGURACIÓN DEL CLIENTE
# ============================================
DEFAULT_CLIENT_HOST = os.getenv('CHAT_CLIENT_HOST', 'localhost')
DEFAULT_CLIENT_PORT = int(os.getenv('CHAT_CLIENT_PORT', '12345'))

# ============================================
# CONFIGURACIÓN DE TIMEOUTS
# ============================================
SOCKET_TIMEOUT = float(os.getenv('CHAT_SOCKET_TIMEOUT', '1.0'))
AUTH_TIMEOUT = float(os.getenv('CHAT_AUTH_TIMEOUT', '10.0'))

# ============================================
# CONFIGURACIÓN DE USUARIOS POR DEFECTO
# ============================================
CREATE_DEFAULT_USERS = os.getenv('CHAT_CREATE_DEFAULT_USERS', 'true').lower() == 'true'

# Lista de usuarios por defecto (solo si CREATE_DEFAULT_USERS=true)
# Formato: usuario1:contraseña1,usuario2:contraseña2
DEFAULT_USERS_STR = os.getenv('CHAT_DEFAULT_USERS', 
    'admin:admin123,user1:pass1,user2:pass2,test:test,alice:1234,beto:4567')

def get_default_users():
    """Parsea y retorna la lista de usuarios por defecto"""
    if not CREATE_DEFAULT_USERS:
        return []
    
    users = []
    for user_pass in DEFAULT_USERS_STR.split(','):
        if ':' in user_pass:
            username, password = user_pass.strip().split(':', 1)
            users.append((username, password))
    return users

# ============================================
# VALIDACIÓN DE CONFIGURACIÓN
# ============================================
def validate_config():
    """Valida que la configuración sea correcta"""
    errors = []
    
    if SERVER_PORT < 1 or SERVER_PORT > 65535:
        errors.append(f"Puerto inválido: {SERVER_PORT}. Debe estar entre 1-65535")
    
    if RSA_KEY_SIZE < 1024:
        errors.append(f"Tamaño de clave RSA muy pequeño: {RSA_KEY_SIZE}. Mínimo 1024 bits")
    
    if LOG_LEVEL not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        errors.append(f"Nivel de log inválido: {LOG_LEVEL}")
    
    return errors

# ============================================
# FUNCIONES DE UTILIDAD
# ============================================
def print_config():
    """Imprime la configuración actual (ocultando contraseñas)"""
    print("=" * 60)
    print("CONFIGURACIÓN DEL CHAT")
    print("=" * 60)
    print(f"Servidor:")
    print(f"  - Host: {SERVER_HOST}")
    print(f"  - Puerto: {SERVER_PORT}")
    print(f"  - Encoding: {SERVER_ENCODING}")
    print(f"\nBase de Datos:")
    print(f"  - Ruta: {DB_PATH}")
    print(f"\nCriptografía:")
    print(f"  - Directorio de claves: {KEYS_DIR}")
    print(f"  - Tamaño de clave RSA: {RSA_KEY_SIZE} bits")
    print(f"\nLogs:")
    print(f"  - Nivel: {LOG_LEVEL}")
    print(f"  - Archivo: {LOG_FILE}")
    print(f"\nUsuarios por defecto:")
    print(f"  - Crear usuarios: {CREATE_DEFAULT_USERS}")
    if CREATE_DEFAULT_USERS:
        users = get_default_users()
        print(f"  - Cantidad: {len(users)}")
    print("=" * 60)

if __name__ == "__main__":
    errors = validate_config()
    if errors:
        print("ERRORES EN CONFIGURACIÓN")
        print("Por favor corrija los siguientes errores:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Configuración válida")
        print_config()