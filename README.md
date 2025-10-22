# Proyecto de Chat Seguro

Este proyecto implementa un servidor y cliente de chat con funcionalidades de canales y autenticación de usuarios.

## Características Principales:

*   **Autenticación Segura**: Utiliza cifrado asimétrico RSA para proteger las contraseñas de los usuarios.
*   **Canales de Chat**: Permite a los usuarios unirse a diferentes canales para organizar las conversaciones.
*   **Mensajes en Tiempo Real**: Comunicación basada en mensajes JSON.
*   **Consola de Administración**: Herramientas para gestionar usuarios y el servidor.

## Control de Versiones y Hashes SHA-256

Para asegurar la integridad del código y documentar los cambios, se mantiene un registro de los hashes SHA-256 de los archivos clave del proyecto.

### HASHES SHA-256 ACTUALES

El listado completo de los hashes SHA-256 de los archivos relevantes se encuentra en `HASHES_SHA256.md` y `hashes.json`.

```
# Hashes SHA-256 de archivos del proyecto

**Total de archivos:** 8

| Archivo | SHA-256 | Tamaño |
|---------|---------|--------|
| `.\change_log.txt` | `f68b15c57f337a177249e1ff8729ad3b2ac9a06ef19729e2707a3f8c26cef16c` | 608 B |
| `.\client.py` | `f2f44a989a6e5e8aa8a8e7cd398d2c71f5efbea7e12e41e88e16f7c31c9c0a07` | 6.7 KB |
| `.\gen_SHA.py` | `b01a572498651bd03a61f4f229da02247ef0e4c64c345e1fb5f6986aee083dc9` | 5.2 KB |
| `.\hashes.json` | `4a8552d138f754a89aa53297100262009a6f7670f16bea1db0719609c9510113` | 1050 B |
| `.\HASHES_SHA256.md` | `30306089339ba254bd0076bcff52bd92458112c4e5ef08b6770a9316a7137977` | 776 B |
| `.\README.md` | `95e5421bf6998c3d57f1f25f2d5d607865527b83ee4bda3dcc61285bf7f29939` | 2.7 KB |
| `.\requirements.txt` | `606a5f5924ecbc2ee87c1f1da2f88c87cb78595b196608ef8828512c97b2bfb0` | 22 B |
| `.\server.py` | `f3ccdde1c03dcd81d59972c1a1b30811ab63a09ed99be0b1ddb9264fa710dd73` | 22.3 KB |

---
*Generado con SHA-256 (256 bits)*
```

## Guía de Inicio Rápido

### Requisitos

*   Python 3.x
*   `pip install -r requirements.txt` para instalar las dependencias (`cryptography`).

### Ejecución del Servidor

1.  Abre una terminal y navega al directorio del proyecto.
2.  Ejecuta: `python server.py`

### Ejecución del Cliente

1.  Abre una **nueva** terminal y navega al directorio del proyecto.
2.  Ejecuta: `python client.py`
3.  Sigue las instrucciones en pantalla para conectarte, autenticarte y unirte a un canal.

## Consola de Administración del Servidor

Desde la terminal del servidor, puedes usar los siguientes comandos:

*   `sys:<msg>`: Envía un mensaje de sistema a todos los clientes.
*   `list`: Muestra los canales activos y los clientes conectados.
*   `shutdown`: Detiene el servidor.
*   `adduser:<user>:<pass>`: Registra un nuevo usuario.
*   `showpass:<user>`: Muestra la contraseña descifrada de un usuario.
*   `showkeys:<user>`: Muestra las rutas a las claves pública y privada de un usuario.
