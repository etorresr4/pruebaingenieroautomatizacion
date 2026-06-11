import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "proveedores.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        if os.path.exists(SCHEMA_PATH):
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
        else:
            # schema.sql no aparece cuando se corre desde otra carpeta, creo las tablas directo
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS proveedores (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    nit_empresa      TEXT    NOT NULL UNIQUE,
                    nombre_empresa   TEXT    NOT NULL,
                    pais             TEXT    NOT NULL,
                    tipo_carga       TEXT    NOT NULL CHECK(tipo_carga IN ('MANUAL', 'AUTOMATICO')),
                    estado_registro  TEXT    NOT NULL CHECK(estado_registro IN ('ACTIVO', 'INACTIVO')),
                    fecha_registro   DATETIME DEFAULT (datetime('now','localtime'))
                );
                CREATE TABLE IF NOT EXISTS archivos_pendientes (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    ruta         TEXT    NOT NULL,
                    estado       TEXT    NOT NULL DEFAULT 'PENDIENTE',
                    fecha_subida DATETIME DEFAULT (datetime('now','localtime'))
                );
            """)
        conn.commit()
        print("BD lista.")
    finally:
        conn.close()
