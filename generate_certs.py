#!/usr/bin/env python3
"""
Generador de certificados SSL para el servidor de chat.
Genera certificados autofirmados para desarrollo/testing.
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta

CERT_DIR = "certs"
CERT_FILE = os.path.join(CERT_DIR, "server.crt")
KEY_FILE = os.path.join(CERT_DIR, "server.key")

def check_openssl():
    """Verifica si OpenSSL está instalado"""
    try:
        result = subprocess.run(
            ["openssl", "version"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✓ OpenSSL encontrado: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("❌ OpenSSL no está instalado")
        print("\nInstala OpenSSL:")
        print("  - Ubuntu/Debian: sudo apt install openssl")
        print("  - macOS: brew install openssl")
        print("  - Windows: https://slproweb.com/products/Win32OpenSSL.html")
        return False
    except subprocess.CalledProcessError:
        print("❌ Error ejecutando OpenSSL")
        return False

def generate_self_signed_cert(days=365, country="MX", org="ChatServer", common_name="localhost"):
    """Genera certificado autofirmado usando OpenSSL"""
    
    print("\n🔐 Generando certificado SSL autofirmado...")
    print("="*60)
    print(f"Validez: {days} días")
    print(f"País: {country}")
    print(f"Organización: {org}")
    print(f"Nombre común: {common_name}")
    print("="*60)
    
    # Crear directorio si no existe
    if not os.path.exists(CERT_DIR):
        os.makedirs(CERT_DIR)
        print(f"✓ Directorio creado: {CERT_DIR}/")
    
    # Construir subject string
    subject = f"/C={country}/O={org}/CN={common_name}"
    
    try:
        # Generar certificado y clave privada
        subprocess.run([
            "openssl", "req",
            "-x509",
            "-newkey", "rsa:4096",
            "-keyout", KEY_FILE,
            "-out", CERT_FILE,
            "-days", str(days),
            "-nodes",
            "-subj", subject
        ], check=True, capture_output=True)
        
        print("\n✓ Certificados generados exitosamente!")
        print(f"\n📄 Archivos creados:")
        print(f"  - Certificado: {CERT_FILE}")
        print(f"  - Clave privada: {KEY_FILE}")
        
        # Mostrar información del certificado
        show_cert_info()
        
        print("\n⚠️  IMPORTANTE:")
        print("  - Este es un certificado AUTOFIRMADO")
        print("  - Solo para desarrollo/testing")
        print("  - Los navegadores mostrarán advertencia de seguridad")
        print("  - Para producción, usa certificados de una CA confiable")
        print("    (ej: Let's Encrypt, Cloudflare, etc.)")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error generando certificado: {e}")
        if e.stderr:
            print(f"   {e.stderr.decode()}")
        return False

def show_cert_info():
    """Muestra información del certificado generado"""
    try:
        result = subprocess.run([
            "openssl", "x509",
            "-in", CERT_FILE,
            "-text",
            "-noout"
        ], capture_output=True, text=True, check=True)
        
        print("\n📋 Información del certificado:")
        print("-"*60)
        
        # Extraer información relevante
        lines = result.stdout.split('\n')
        for line in lines:
            if 'Subject:' in line or 'Issuer:' in line:
                print(f"  {line.strip()}")
            elif 'Not Before:' in line or 'Not After:' in line:
                print(f"  {line.strip()}")
            elif 'Public-Key:' in line:
                print(f"  {line.strip()}")
        
        print("-"*60)
        
    except subprocess.CalledProcessError:
        print("⚠️  No se pudo leer información del certificado")

def generate_production_cert_guide():
    """Muestra guía para generar certificados de producción"""
    print("\n📚 Guía para certificados de PRODUCCIÓN")
    print("="*60)
    
    print("\n1️⃣  Let's Encrypt (GRATIS):")
    print("   - Instala Certbot: https://certbot.eff.org/")
    print("   - Ejecuta: sudo certbot certonly --standalone -d tudominio.com")
    print("   - Certificados en: /etc/letsencrypt/live/tudominio.com/")
    
    print("\n2️⃣  Cloudflare (GRATIS):")
    print("   - Regístrate en https://cloudflare.com")
    print("   - Agrega tu dominio")
    print("   - Usa Cloudflare Tunnel para conexiones seguras")
    
    print("\n3️⃣  Certificados comerciales:")
    print("   - DigiCert, GlobalSign, Sectigo, etc.")
    print("   - Compra certificado según tus necesidades")
    
    print("\n4️⃣  Para uso interno/corporativo:")
    print("   - Crea tu propia CA (Certificate Authority)")
    print("   - Distribuye el certificado raíz a los clientes")
    
    print("="*60)

def main():
    print("🔐 Generador de Certificados SSL")
    print("="*60)
    
    # Verificar OpenSSL
    if not check_openssl():
        return 1
    
    # Verificar si ya existen certificados
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print(f"\n⚠️  Ya existen certificados en {CERT_DIR}/")
        response = input("¿Deseas regenerarlos? (s/N): ").strip().lower()
        if response != 's':
            print("Operación cancelada")
            show_cert_info()
            return 0
    
    print("\n⚙️  Configuración del certificado:")
    
    # Solicitar configuración
    days = input("Días de validez (Enter = 365): ").strip()
    days = int(days) if days.isdigit() else 365
    
    country = input("Código de país (Enter = MX): ").strip() or "MX"
    org = input("Organización (Enter = ChatServer): ").strip() or "ChatServer"
    common_name = input("Nombre común/dominio (Enter = localhost): ").strip() or "localhost"
    
    # Generar certificado
    if generate_self_signed_cert(days, country, org, common_name):
        print("\n✅ Proceso completado exitosamente")
        
        # Preguntar si quiere ver la guía de producción
        print("\n" + "-"*60)
        response = input("¿Ver guía para certificados de producción? (s/N): ").strip().lower()
        if response == 's':
            generate_production_cert_guide()
        
        return 0
    else:
        print("\n❌ Error generando certificados")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Operación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)