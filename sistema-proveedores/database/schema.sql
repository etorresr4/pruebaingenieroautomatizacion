-- ============================================================
-- Script de creación de base de datos
-- Sistema Híbrido de Gestión de Proveedores
-- ============================================================

-- Tabla principal de proveedores
CREATE TABLE IF NOT EXISTS proveedores (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nit_empresa      TEXT    NOT NULL UNIQUE,
    nombre_empresa   TEXT    NOT NULL,
    pais             TEXT    NOT NULL,
    tipo_carga       TEXT    NOT NULL CHECK(tipo_carga IN ('MANUAL', 'AUTOMATICO')),
    estado_registro  TEXT    NOT NULL CHECK(estado_registro IN ('ACTIVO', 'INACTIVO')),
    fecha_registro   DATETIME DEFAULT (datetime('now','localtime'))
);

-- Tabla de control de archivos pendientes para el robot RPA
CREATE TABLE IF NOT EXISTS archivos_pendientes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta         TEXT    NOT NULL,
    estado       TEXT    NOT NULL DEFAULT 'PENDIENTE',
    -- estados posibles: PENDIENTE → PROCESANDO → COMPLETADO
    fecha_subida DATETIME DEFAULT (datetime('now','localtime'))
);
