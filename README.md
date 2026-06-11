# Sistema Híbrido de Gestión de Proveedores

Aplicación web para registrar proveedores de dos formas: manualmente desde un formulario, o subiendo un archivo Excel/CSV que procesa un robot por separado.

---

## Tecnologías

| Capa | Tecnología |
|---|---|
| Backend / API | Python 3.10+ · FastAPI · Uvicorn |
| Base de datos | SQLite |
| Frontend | HTML + CSS + JavaScript |
| Robot | Python · Pandas · Requests |

---

## Estructura del proyecto

```
sistema-proveedores/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── proveedores.db        ← se crea sola al levantar el backend
│   └── uploads/
├── database/
│   └── schema.sql
├── frontend/
│   └── index.html
├── robot/
│   └── robot.py
└── archivos_prueba/
    └── proveedores_prueba.xlsx
```

---

## Requisitos

- Python 3.10 o superior → [python.org/downloads](https://www.python.org/downloads/)
- En Windows marcar **"Add Python to PATH"** durante la instalación

Verificar:
```bash
python --version
```

---

## Instalación

### 1. Clonar o descargar el proyecto

```bash
git clone git clone https://github.com/etorresr4/pruebaingenieroautomatizacion.git
cd sistema-proveedores
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
cd backend
pip install -r requirements.txt
```

---

## Cómo levantar el sistema

Necesitás **2 terminales** abiertas al mismo tiempo.

---

### Terminal 1 — Backend

```bash
cd backend
uvicorn main:app --reload
```

Salida esperada:
```
BD lista.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

### Navegador — Frontend

Abrir `frontend/index.html` directo en Chrome puede fallar por políticas de seguridad. Lo más fácil es:

```bash
cd frontend
python -m http.server 5500
```

Luego abrir: [http://localhost:5500](http://localhost:5500)

También funciona con la extensión **Live Server** de VS Code, o haciendo doble clic en Firefox.

---

### Terminal 2 — Robot

```bash
cd robot
python robot.py
```

Salida esperada:
```
Robot iniciado. Monitoreando archivos...
Sin archivos. Revisando en 5s...
```

El robot revisa cada 5 segundos si hay un archivo para procesar.

---

## Probar el flujo completo

### Flujo 1 — Registro manual

1. Llenar el formulario (NIT, Nombre, País, Estado)
2. Clic en **Registrar Proveedor**
3. El proveedor aparece en la tabla con badge **Manual**

---

### Flujo 2 — Carga con el robot

1. Confirmar que el robot esté corriendo en Terminal 2
2. En la web, sección **Carga Automática**:
   - Seleccionar `archivos_prueba/proveedores_prueba.xlsx`
   - Clic en **Enviar al Robot**
3. El indicador cambia:
   ```
   Pendiente → Procesando → Completado
   ```
4. En Terminal 2 se ve:
   ```
   [robot] encontre archivo: .../proveedores_prueba.xlsx
   [robot] 6 filas, columnas: ['nit_empresa', 'nombre_empresa', 'pais', 'estado_registro']
   [robot] validos: 5 | saltados: 1
   [robot] listo! insertados=5 duplicados=0
   ```
5. Los proveedores aparecen en la tabla con badge **Automático** (5 registros, la fila sin NIT fue saltada)

---

### Flujo 3 — Edición

1. Clic en cualquier fila de la tabla
2. Se abre un modal
3. Se pueden editar **Nombre** y **Estado** (el NIT no se puede cambiar)
4. Clic en **Guardar cambios**

---

## Formato del archivo

El CSV o Excel necesita estas columnas:

| Columna | Obligatorio | Notas |
|---|---|---|
| `nit_empresa` | Sí | Letras, números, guiones y puntos |
| `nombre_empresa` | Sí | Mínimo 2 caracteres |
| `pais` | Sí | Sin números |
| `estado_registro` | No | `ACTIVO` o `INACTIVO` (default: ACTIVO) |

Filas con campos vacíos se saltan sin cancelar todo el proceso. NITs duplicados también se omiten.

---

## Endpoints

| Método | Endpoint | Qué hace |
|---|---|---|
| POST | `/api/proveedores/manual` | Registra un proveedor desde el formulario |
| POST | `/api/proveedores/upload-archivo` | Recibe el archivo |
| GET | `/api/proveedores` | Lista todos los proveedores |
| PUT | `/api/proveedores/{id}` | Edita nombre y estado |
| GET | `/api/robot/archivo-pendiente` | El robot consulta si hay trabajo |
| POST | `/api/robot/insertar-masivo` | El robot manda los datos del archivo |
| GET | `/api/robot/estado-archivo` | Estado del archivo actual |

Documentación interactiva: `http://127.0.0.1:8000/docs`

---

## Variables de entorno del robot

| Variable | Default | Descripción |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8000` | URL del backend |
| `INTERVALO_SEGUNDOS` | `5` | Cada cuánto revisa si hay archivos |

Ejemplo:
```bash
# macOS / Linux:
export BACKEND_URL=http://192.168.1.100:8000
python robot.py

# Windows:
set BACKEND_URL=http://192.168.1.100:8000
python robot.py
```

---

## Problemas comunes

**El frontend no conecta con el backend**
Verificar que uvicorn esté corriendo en Terminal 1 y que el frontend esté en un servidor local, no abierto desde `file://`.

**`database is locked`**
Pasa cuando el robot y alguien en la web escriben al mismo tiempo. El backend devuelve un 503 con mensaje. Solo hay que esperar un momento y volver a intentar.

**El robot no detecta archivos**
Revisar que el backend esté corriendo y que `BACKEND_URL` apunte bien. El robot imprime en consola cada 5 segundos — si hay error de conexión lo dice ahí.

**Puerto 8000 ocupado**
```bash
uvicorn main:app --reload --port 8001
```
Actualizar `BACKEND_URL` en `robot.py` al nuevo puerto.

---

## Por qué hice algunas cosas así

Usé SQLite porque no requiere instalar nada aparte — el archivo `.db` se crea solo, lo que hace más fácil probar el proyecto.

La tabla `archivos_pendientes` existe para que el robot no tenga que saber nada del frontend ni viceversa. El frontend registra que hay un archivo listo, el robot lo detecta, lo procesa y actualiza el estado. Si el robot corre en otra máquina también funciona igual.

El robot es un script separado porque la prueba pedía que fuera un agente externo. Si lo hubiera metido dentro del backend como una función más, técnicamente haría lo mismo pero no cumpliría ese requisito.

El error `database is locked` lo captura el backend y devuelve un 503 con texto legible en vez de que la petición falle sin explicación.

---

## Autor

Desarrollado como prueba técnica para la vacante de Ingeniero de Automatización · Américas BPS
