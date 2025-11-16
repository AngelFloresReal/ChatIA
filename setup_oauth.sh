#!/bin/bash

echo "================================================"
echo "  Configuración de OAuth 2.0 para Chat App"
echo "================================================"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no está instalado"
    exit 1
fi

echo "✓ Python 3 encontrado"

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "📦 Creando entorno virtual..."
    python3 -m venv venv
fi

# Activar entorno virtual
echo "🔄 Activando entorno virtual..."
source venv/bin/activate

# Instalar dependencias
echo "📥 Instalando dependencias de OAuth..."
pip install --upgrade pip
pip install google-auth google-auth-oauthlib google-auth-httplib2

echo ""
echo "✓ Dependencias instaladas correctamente"
echo ""

# Actualizar base de datos
echo "🗄️  Actualizando esquema de base de datos..."
python3 << 'PYTHON_SCRIPT'
import sqlite3
import os

DB_PATH = "chat.db"

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verificar si las columnas ya existen
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'email' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN email TEXT')
        print("  ✓ Columna 'email' agregada")
    
    if 'oauth_provider' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN oauth_provider TEXT')
        print("  ✓ Columna 'oauth_provider' agregada")
    
    conn.commit()
    conn.close()
    print("✓ Base de datos actualizada")
else:
    print("⚠️  Base de datos no encontrada. Se creará al iniciar el servidor.")

PYTHON_SCRIPT

echo ""
echo "================================================"
echo "  Configuración de Google Cloud Console"
echo "================================================"
echo ""
echo "Para completar la configuración necesitas:"
echo ""
echo "1. Ir a: https://console.cloud.google.com"
echo "2. Crear un nuevo proyecto (o usar uno existente)"
echo "3. Habilitar 'Google+ API' en 'APIs y Servicios'"
echo "4. Ir a 'Credenciales' → 'Crear credenciales'"
echo "5. Seleccionar 'ID de cliente de OAuth 2.0'"
echo "6. Tipo de aplicación: 'Aplicación de escritorio'"
echo "7. Copiar el CLIENT_ID y CLIENT_SECRET"
echo ""
echo "Luego edita el archivo 'config_oauth.py' y reemplaza:"
echo "  - GOOGLE_CLIENT_ID"
echo "  - GOOGLE_CLIENT_SECRET"
echo ""
echo "================================================"
echo "  Archivos a modificar"
echo "================================================"
echo ""
echo "1. Crea 'config_oauth.py' con las credenciales"
echo "2. Modifica 'server.py' agregando el código de 'server_oauth.py'"
echo "3. Usa 'client_oauth.py' para conectarte con OAuth"
echo ""
echo "✓ Setup completado!"
echo ""