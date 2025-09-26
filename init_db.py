import sqlite3

conn = sqlite3.connect("chat.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")

# Insertar usuarios de ejemplo
c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("alice", "1234"))
c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("beto", "4567"))
c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("admin", "adminpass"))

conn.commit()
conn.close()
print("Base de datos inicializada")