from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from contextlib import asynccontextmanager
import logging
import re
import os
import shutil

from database import get_connection, init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sistema de Proveedores", version="1.0.0", lifespan=lifespan)

# TODO: cambiar esto en produccion
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOADS, exist_ok=True)

NIT_RE = re.compile(r'^[A-Za-z0-9\-\.]{3,30}$')

# tiempo máximo en PROCESANDO antes de considerarlo caído y reintentarlo
TIMEOUT_PROC = 120


class NuevoProveedor(BaseModel):
    nit_empresa: str
    nombre_empresa: str
    pais: str
    estado_registro: str

    @field_validator('nit_empresa')
    @classmethod
    def check_nit(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('NIT vacío')
        if not NIT_RE.match(v):
            raise ValueError('NIT inválido')
        return v

    @field_validator('nombre_empresa')
    @classmethod
    def check_nombre(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError('nombre muy corto')
        if len(v) > 150:
            raise ValueError('nombre muy largo')
        return v

    @field_validator('pais')
    @classmethod
    def check_pais(cls, v):
        v = v.strip()
        if len(v) < 2 or len(v) > 60:
            raise ValueError('país inválido')
        if re.search(r'\d', v):
            raise ValueError('el país no puede tener números')
        return v

    @field_validator('estado_registro')
    @classmethod
    def check_estado(cls, v):
        v = v.strip().upper()
        if v not in ('ACTIVO', 'INACTIVO'):
            raise ValueError('estado debe ser ACTIVO o INACTIVO')
        return v


class EdicionProveedor(BaseModel):
    nombre_empresa: str
    estado_registro: str

    @field_validator('nombre_empresa')
    @classmethod
    def check_nombre(cls, v):
        v = v.strip()
        if not (2 <= len(v) <= 150):
            raise ValueError('nombre inválido')
        return v

    @field_validator('estado_registro')
    @classmethod
    def check_estado(cls, v):
        v = v.strip().upper()
        if v not in ('ACTIVO', 'INACTIVO'):
            raise ValueError('estado inválido')
        return v


class LoteMasivo(BaseModel):
    proveedores: list[dict]

    @field_validator('proveedores')
    @classmethod
    def check_lista(cls, v):
        if not v:
            raise ValueError('lista vacía')
        if len(v) > 1000:
            raise ValueError('máximo 1000 por lote')
        return v


def limpiar_fila(p: dict, fila: int) -> dict:
    nit = str(p.get("nit_empresa", "")).strip()
    if not nit or not NIT_RE.match(nit):
        raise ValueError(f"fila {fila}: NIT inválido")

    nombre = str(p.get("nombre_empresa", "")).strip()
    if not nombre or len(nombre) < 2:
        raise ValueError(f"fila {fila}: nombre inválido")

    pais = str(p.get("pais", "")).strip()
    if not pais or len(pais) < 2 or re.search(r'\d', pais):
        raise ValueError(f"fila {fila}: país inválido")

    estado = str(p.get("estado_registro", "ACTIVO")).strip().upper()
    if estado not in ("ACTIVO", "INACTIVO"):
        estado = "ACTIVO"

    return {"nit_empresa": nit, "nombre_empresa": nombre, "pais": pais, "estado_registro": estado}


def resetear_colgados(conn):
    conn.execute(
        """
        UPDATE archivos_pendientes
        SET estado = 'PENDIENTE'
        WHERE estado = 'PROCESANDO'
          AND (julianday('now') - julianday(fecha_subida)) * 86400 > ?
        """,
        (TIMEOUT_PROC,)
    )
    conn.commit()


@app.post("/api/proveedores/manual")
def crear_proveedor(data: NuevoProveedor):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO proveedores (nit_empresa, nombre_empresa, pais, tipo_carga, estado_registro) VALUES (?, ?, ?, 'MANUAL', ?)",
            (data.nit_empresa, data.nombre_empresa, data.pais, data.estado_registro)
        )
        conn.commit()
        log.info(f"proveedor creado: {data.nit_empresa}")
        return {"mensaje": "Proveedor registrado", "tipo_carga": "MANUAL"}
    except Exception as e:
        conn.rollback()
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=409, detail=f"el NIT {data.nit_empresa} ya existe")
        log.error(f"error al crear proveedor: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/proveedores/upload-archivo")
def recibir_archivo(archivo: UploadFile = File(...)):
    if not archivo.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="solo .xlsx, .xls o .csv")

    nombre = re.sub(r'[^A-Za-z0-9_\-\.]', '_', archivo.filename)
    destino = os.path.join(UPLOADS, nombre)

    with open(destino, "wb") as f:
        shutil.copyfileobj(archivo.file, f)

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO archivos_pendientes (ruta, estado) VALUES (?, 'PENDIENTE')",
            (destino,)
        )
        conn.commit()
        log.info(f"archivo recibido: {nombre}")
        return {"mensaje": "Archivo recibido, el robot lo procesará pronto.", "estado": "PENDIENTE"}
    finally:
        conn.close()


@app.get("/api/proveedores")
def get_proveedores():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT id, nit_empresa, nombre_empresa, pais,
                   tipo_carga, estado_registro, fecha_registro
            FROM proveedores
            ORDER BY fecha_registro DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.put("/api/proveedores/{id}")
def actualizar_proveedor(id: int, data: EdicionProveedor):
    conn = get_connection()
    try:
        existe = conn.execute("SELECT id FROM proveedores WHERE id = ?", (id,)).fetchone()
        if not existe:
            raise HTTPException(status_code=404, detail=f"proveedor {id} no encontrado")

        conn.execute(
            "UPDATE proveedores SET nombre_empresa = ?, estado_registro = ? WHERE id = ?",
            (data.nombre_empresa, data.estado_registro, id)
        )
        conn.commit()
        return {"mensaje": "Proveedor actualizado"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        # pasa cuando el robot escribe al mismo tiempo
        if "locked" in str(e).lower():
            raise HTTPException(status_code=503, detail="BD ocupada, intentá de nuevo")
        log.error(f"error al actualizar {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/robot/archivo-pendiente")
def siguiente_archivo():
    conn = get_connection()
    try:
        resetear_colgados(conn)

        row = conn.execute(
            "SELECT id, ruta FROM archivos_pendientes WHERE estado = 'PENDIENTE' ORDER BY id DESC LIMIT 1"
        ).fetchone()

        if row:
            conn.execute(
                "UPDATE archivos_pendientes SET estado = 'PROCESANDO' WHERE id = ?", (row["id"],)
            )
            conn.commit()
            log.info(f"archivo asignado al robot: {row['ruta']}")
            return {"hay_archivo": True, "id": row["id"], "ruta": row["ruta"]}
        return {"hay_archivo": False}
    finally:
        conn.close()


@app.post("/api/robot/insertar-masivo")
def insertar_lote(payload: LoteMasivo):
    ok = 0
    dup = 0
    errores = []

    conn = get_connection()
    try:
        for i, p in enumerate(payload.proveedores):
            try:
                fila = limpiar_fila(p, i + 2)
                conn.execute(
                    "INSERT INTO proveedores (nit_empresa, nombre_empresa, pais, tipo_carga, estado_registro) VALUES (?, ?, ?, 'AUTOMATICO', ?)",
                    (fila["nit_empresa"], fila["nombre_empresa"], fila["pais"], fila["estado_registro"])
                )
                ok += 1
            except ValueError as e:
                errores.append({"fila": i + 2, "error": str(e)})
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    dup += 1
                else:
                    errores.append({"nit": p.get("nit_empresa"), "error": str(e)})

        conn.execute("UPDATE archivos_pendientes SET estado = 'COMPLETADO' WHERE estado = 'PROCESANDO'")
        conn.commit()
        log.info(f"lote procesado: {ok} insertados, {dup} duplicados, {len(errores)} errores")

        return {"mensaje": "Listo", "insertados": ok, "omitidos_por_nit_duplicado": dup, "errores": errores}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/robot/estado-archivo")
def estado_ultimo_archivo():
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT estado FROM archivos_pendientes ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return {"estado": row["estado"] if row else None}
    finally:
        conn.close()
