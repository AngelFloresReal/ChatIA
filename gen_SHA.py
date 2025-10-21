"""
Generador de hashes SHA-256 para archivos del proyecto
Versión mejorada del código MD5 usando SHA-256
"""
import os
import hashlib

def sha256_de_archivo(ruta_archivo):
    """Calcula el hash SHA-256 de un archivo"""
    hash_sha256 = hashlib.sha256()
    
    with open(ruta_archivo, "rb") as f:
        # Leer en bloques de 4KB para eficiencia
        for bloque in iter(lambda: f.read(4096), b""):
            hash_sha256.update(bloque)
    
    return hash_sha256.hexdigest()

def obtener_hashes_en_directorio(directorio, ignorar_carpetas=None, extensiones_ignoradas=None):
    """
    Recorre el directorio y obtiene los hashes SHA-256 de todos los archivos,
    ignorando carpetas y extensiones específicas.
    """
    if ignorar_carpetas is None:
        ignorar_carpetas = {'.git', '__pycache__', 'venv', 'node_modules', 'user_keys'}
    
    if extensiones_ignoradas is None:
        extensiones_ignoradas = {'.pyc', '.log', '.tmp', '.pem', '.db'}

    resultados = []
    
    for raiz, dirs, archivos in os.walk(directorio):
        # Filtrar directorios a ignorar
        dirs[:] = [d for d in dirs if d not in ignorar_carpetas]

        for archivo in archivos:
            ruta = os.path.join(raiz, archivo)
            
            # Ignorar por extensión
            if any(archivo.endswith(ext) for ext in extensiones_ignoradas):
                continue
            
            try:
                hash_sha256 = sha256_de_archivo(ruta)
                tamaño = os.path.getsize(ruta)
                resultados.append((ruta, hash_sha256, tamaño))
                print(f"✓ {ruta}")
                
            except Exception as e:
                print(f"⚠️  Error con {ruta}: {e}")
    
    return resultados

def escribir_readme(resultados, salida="HASHES_SHA256.md"):
    """Escribe los resultados en formato Markdown"""
    with open(salida, "w", encoding="utf-8") as f:
        f.write("# Hashes SHA-256 de archivos del proyecto\n\n")
        f.write(f"**Total de archivos:** {len(resultados)}\n\n")
        f.write("| Archivo | SHA-256 | Tamaño |\n")
        f.write("|---------|---------|--------|\n")
        
        for ruta, hash_sha256, tamaño in resultados:
            # Formatear tamaño
            if tamaño < 1024:
                tam_str = f"{tamaño} B"
            elif tamaño < 1024 * 1024:
                tam_str = f"{tamaño / 1024:.1f} KB"
            else:
                tam_str = f"{tamaño / (1024 * 1024):.2f} MB"
            
            f.write(f"| `{ruta}` | `{hash_sha256}` | {tam_str} |\n")
        
        f.write("\n---\n")
        f.write("*Generado con SHA-256 (256 bits)*\n")

def escribir_json(resultados, salida="hashes.json"):
    """Escribe los resultados en formato JSON para procesamiento automático"""
    import json
    
    datos = {
        "algoritmo": "SHA-256",
        "total_archivos": len(resultados),
        "archivos": [
            {
                "ruta": ruta,
                "sha256": hash_val,
                "tamaño_bytes": tamaño
            }
            for ruta, hash_val, tamaño in resultados
        ]
    }
    
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)

def comparar_hashes(archivo_json):
    """Compara hashes actuales con hashes guardados"""
    import json
    
    try:
        with open(archivo_json, "r", encoding="utf-8") as f:
            datos_previos = json.load(f)
        
        hashes_previos = {
            item["ruta"]: item["sha256"]
            for item in datos_previos["archivos"]
        }
        
        resultados_actuales = obtener_hashes_en_directorio(".")
        
        print("\n=== Comparación de Integridad ===\n")
        
        cambios = 0
        for ruta, hash_actual, _ in resultados_actuales:
            if ruta in hashes_previos:
                if hashes_previos[ruta] != hash_actual:
                    print(f"⚠️  MODIFICADO: {ruta}")
                    cambios += 1
            else:
                print(f"✨ NUEVO: {ruta}")
        
        for ruta_previa in hashes_previos:
            if not any(ruta == ruta_previa for ruta, _, _ in resultados_actuales):
                print(f"🗑️  ELIMINADO: {ruta_previa}")
        
        if cambios == 0:
            print("✓ Todos los archivos mantienen su integridad")
        else:
            print(f"\n⚠️  {cambios} archivo(s) modificado(s)")
        
    except FileNotFoundError:
        print(f"⚠️  No se encontró {archivo_json}")

if __name__ == "__main__":
    import sys
    
    print("🔐 Generador de Hashes SHA-256")
    print("=" * 50)
    
    proyecto = "."
    
    # Generar hashes
    resultados = obtener_hashes_en_directorio(proyecto)
    
    print(f"\n✓ {len(resultados)} archivos procesados")
    
    # Escribir en Markdown
    escribir_readme(resultados)
    print("✓ Hashes guardados en HASHES_SHA256.md")
    
    # Escribir en JSON
    escribir_json(resultados)
    print("✓ Hashes guardados en hashes.json")
    
    # Si se pasa argumento 'compare', comparar con hashes previos
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        comparar_hashes("hashes.json")