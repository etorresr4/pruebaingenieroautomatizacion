import requests
import pandas as pd
import time
import os

BASE_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
SLEEP = int(os.environ.get("INTERVALO_SEGUNDOS", 5))
MAX_INT = int(os.environ.get("MAX_REINTENTOS", 3))

print("[robot] iniciado, backend:", BASE_URL)

while True:
    # consultar si hay archivo
    archivo_ruta = None
    try:
        resp = requests.get(f"{BASE_URL}/api/robot/archivo-pendiente", timeout=5)
        info = resp.json()
        if info.get("hay_archivo"):
            archivo_ruta = info["ruta"]
            print("[robot] encontre archivo:", archivo_ruta)
    except Exception as ex:
        print("[robot] no pude conectar al backend:", ex)
        time.sleep(SLEEP)
        continue

    if not archivo_ruta:
        print(f"[robot] nada por ahora, espero {SLEEP}s")
        time.sleep(SLEEP)
        continue

    # leer el archivo
    df = None
    ext = os.path.splitext(archivo_ruta)[1].lower()
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(archivo_ruta)
        elif ext == ".csv":
            df = pd.read_csv(archivo_ruta)
            # si solo viene una columna probablemente el separador es ; (excel en español)
            if len(df.columns) == 1:
                df = pd.read_csv(archivo_ruta, sep=";")
        else:
            print("[robot] formato no soportado:", ext)
    except Exception as ex:
        print("[robot] error leyendo archivo:", ex)

    if df is None:
        time.sleep(SLEEP)
        continue

    print(f"[robot] {len(df)} filas, columnas: {list(df.columns)}")

    # normalizar headers
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # pandas a veces lee nit como 123456.0 si hay celdas vacias en la columna
    if "nit_empresa" in df.columns:
        df["nit_empresa"] = df["nit_empresa"].astype(str).str.replace(r'\.0$', '', regex=True)

    # armar lista de proveedores validos
    lista = []
    saltados = 0
    for idx, row in df.iterrows():
        n = idx + 2  # +2 porque fila 1 es header en excel

        nit = str(row.get("nit_empresa", "")).strip()
        if not nit or nit == "nan":
            saltados += 1
            continue

        nombre = str(row.get("nombre_empresa", "")).strip()
        if not nombre or nombre == "nan":
            saltados += 1
            continue

        pais = str(row.get("pais", "")).strip()
        if not pais or pais == "nan":
            saltados += 1
            continue

        estado = str(row.get("estado_registro", "ACTIVO")).strip().upper()
        if estado not in ("ACTIVO", "INACTIVO"):
            estado = "ACTIVO"

        lista.append({
            "nit_empresa": nit,
            "nombre_empresa": nombre,
            "pais": pais,
            "estado_registro": estado
        })

    print(f"[robot] validos: {len(lista)} | saltados: {saltados}")

    if not lista:
        print("[robot] no habia nada util en el archivo")
        time.sleep(SLEEP)
        continue

    # enviar al backend con reintentos
    enviado = False
    for intento in range(1, MAX_INT + 1):
        try:
            r = requests.post(
                f"{BASE_URL}/api/robot/insertar-masivo",
                json={"proveedores": lista},
                timeout=30
            )
            if r.status_code == 200:
                res = r.json()
                print(f"[robot] listo! insertados={res.get('insertados')} duplicados={res.get('omitidos_por_nit_duplicado')}")
                if res.get("errores"):
                    print("[robot] algunas filas fallaron:", res["errores"])
                enviado = True
                break
            elif r.status_code == 422:
                print("[robot] backend rechazo los datos, no reintento:", r.text[:200])
                break
            else:
                print(f"[robot] intento {intento}: status raro {r.status_code}")
        except requests.exceptions.Timeout:
            print(f"[robot] intento {intento}: timeout")
        except Exception as ex:
            print(f"[robot] intento {intento}: {ex}")

        if intento < MAX_INT:
            time.sleep(intento * 3)

    if not enviado:
        print("[robot] no pude enviar, el backend va a resetear el archivo cuando pase el timeout")

    time.sleep(SLEEP)
