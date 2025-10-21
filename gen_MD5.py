import os
import hashlib

def md5_de_archivo(ruta_archivo):
    hash_md5 = hashlib.md5()
    with open(ruta_archivo, "rb") as f:
        for bloque in iter(lambda: f.read(4096), b""):
            hash_md5.update(bloque)
    return hash_md5.hexdigest()

def obtener_hashes_en_directorio(directorio, ignorar_carpetas=None, extensiones_ignoradas=None):
    """Recorre el directorio y obtiene los hashes de todos los archivos, ignorando carpetas específicas."""
    if ignorar_carpetas is None:
        ignorar_carpetas = {'.git', '__pycache__', 'venv'}
    if extensiones_ignoradas is None:
        extensiones_ignoradas = {'.pyc', '.log', '.tmp'}

    resultados = []
    for raiz, dirs, archivos in os.walk(directorio):
        dirs[:] = [d for d in dirs if d not in ignorar_carpetas]

        for archivo in archivos:
            ruta = os.path.join(raiz, archivo)
            if any(archivo.endswith(ext) for ext in extensiones_ignoradas):
                continue
            try:
                hash_md5 = md5_de_archivo(ruta)
                resultados.append((ruta, hash_md5))
            except Exception as e:
                print(f"⚠️ Error con {ruta}: {e}")
    return resultados

def escribir_readme(resultados, salida="README.md"):
    with open(salida, "w", encoding="utf-8") as f:
        f.write("# Hash MD5 de archivos del proyecto\n\n")
        f.write("| Archivo | MD5 |\n")
        f.write("|----------|-----|\n")
        for ruta, hash_md5 in resultados:
            f.write(f"| `{ruta}` | `{hash_md5}` |\n")

if __name__ == "__main__":
    proyecto = "."
    resultados = obtener_hashes_en_directorio(proyecto)
    escribir_readme(resultados)
    print("Hashes MD5 generados")
