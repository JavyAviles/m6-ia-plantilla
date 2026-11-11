"""
curso.py — Funciones de apoyo del Módulo 6 (Diplomado en Big Data e IA · CEC-EPN)
Ing. Eduardo Avilés

Contiene:
  * APIPagoYa          : API REST simulada de la app de pagos móviles «PagoYa» (datos ficticios).
  * descargar_todo     : descarga todas las páginas de un endpoint y devuelve la lista de eventos JSON.
  * eda_rapido         : diagnóstico automático de calidad de datos (EDA).
  * registrar/checkpoint/resumen : registro del estudiante y validación de los checkpoints de clase.
Todos los datos son SIMULADOS con fines didácticos.
"""
import hashlib, json, math, base64
import numpy as np
import pandas as pd

VERSION = "m6-2026.11"

# ---------------------------------------------------------------------------
# 1. API simulada de la app «PagoYa»
# ---------------------------------------------------------------------------
_PROV = ["Pichincha", "Guayas", "Azuay", "Manabí", "El Oro", "Loja", "Tungurahua", "Imbabura"]
_TIPOS = ["pago_comercio", "transferencia", "recarga", "retiro_agente"]
_CATS = {"pago_comercio": ["supermercado", "farmacia", "restaurante", "tecnologia", "ropa"],
         "transferencia": ["persona"], "recarga": ["telefonia"], "retiro_agente": ["efectivo"]}


def _generar_eventos(n=3000, seed=2026):
    rng = np.random.default_rng(seed)
    nu = 800
    usuarios = pd.DataFrame({
        "id": [f"U{i:04d}" for i in range(nu)],
        "edad": rng.integers(18, 71, nu),
        "provincia": rng.choice(_PROV, nu, p=[.30, .28, .10, .09, .07, .06, .05, .05]),
        "antiguedad_meses": rng.integers(1, 61, nu),
        "ingreso_mensual": np.round(np.exp(rng.normal(6.75, 0.45, nu)), 2),
    })
    u = rng.integers(0, nu, n)
    seg = rng.integers(0, 61 * 24 * 3600, n)
    hora_p = np.array([2.2, 1.8, 1.5, 1.3, 1.2, 1.2, 1.5, 3, 4.5, 5, 5, 5.5, 6, 5.5, 5, 5, 5, 5.5, 6, 6, 5, 4, 3, 2], float)
    hora = rng.choice(24, n, p=hora_p / hora_p.sum())
    ts = pd.Timestamp("2026-09-01") + pd.to_timedelta(seg // 86400, unit="D") + pd.to_timedelta(hora, unit="h") \
        + pd.to_timedelta(rng.integers(0, 3600, n), unit="s")
    tipo = rng.choice(_TIPOS, n, p=[.45, .30, .15, .10])
    ing = usuarios["ingreso_mensual"].values[u]
    base = {"pago_comercio": .05, "transferencia": .12, "recarga": .015, "retiro_agente": .10}
    monto = np.array([base[t] for t in tipo]) * ing * np.exp(rng.normal(0, .55, n))
    nuevo = rng.random(n) < .15
    dist = np.round(rng.exponential(6, n), 1)
    intentos = rng.choice([1, 2, 3], n, p=[.80, .12, .08])
    edad = usuarios["edad"].values[u]
    # fraude: patrón NO lineal (interacciones): dispositivo nuevo lejos de casa, monto alto de madrugada, PIN fallido en adultos mayores
    noche = (hora <= 5)
    ratio = monto / ing
    z = (-4.0 + 5.0 * (nuevo & (dist > 5)) + 5.0 * ((ratio > .10) & noche) + 4.5 * ((intentos == 3) & (edad > 50)))
    pfraude = 1 / (1 + np.exp(-z))
    fraude = (rng.random(n) < pfraude).astype(int)
    monto = np.where(fraude == 1, monto * rng.uniform(1.2, 2.2, n), monto)
    ev = []
    for i in range(n):
        us = usuarios.iloc[u[i]]
        cat = rng.choice(_CATS[tipo[i]])
        ev.append({
            "evento_id": f"TX-{i:06d}",
            "timestamp": ts[i].strftime("%Y-%m-%dT%H:%M:%S-05:00"),
            "usuario": {"id": us["id"], "edad": int(us["edad"]), "provincia": us["provincia"],
                        "antiguedad_meses": int(us["antiguedad_meses"]), "ingreso_mensual": float(us["ingreso_mensual"])},
            "transaccion": {"tipo": tipo[i], "canal": str(rng.choice(["app", "web"], p=[.82, .18])),
                            "categoria": str(cat), "monto": round(float(monto[i]), 2)},
            "contexto": {"dispositivo_nuevo": bool(nuevo[i]), "distancia_km": float(dist[i]), "intentos_pin": int(intentos[i])},
            "etiqueta": {"fraude": int(fraude[i])},
        })
    # problemas de calidad sembrados (como en una app real)
    for i in rng.choice(n, 30, replace=False):
        ev[i]["usuario"]["edad"] = None                      # edad no registrada
    for i in rng.choice(n, 4, replace=False):
        ev[i]["transaccion"]["monto"] = -abs(ev[i]["transaccion"]["monto"])   # reversos mal etiquetados
    for i in rng.choice(n, 6, replace=False):
        ev.append(json.loads(json.dumps(ev[i])))           # eventos reenviados (duplicados)
    return ev


class APIPagoYa:
    """API REST SIMULADA de la app de pagos móviles «PagoYa».
    Imita lo que devolvería  GET https://api.pagoya.ec/v1/transacciones?pagina=1&por_pagina=500
    """
    BASE_URL = "https://api.pagoya.ec"     # dirección ficticia: no existe en internet

    def __init__(self, seed=2026):
        self._eventos = _generar_eventos(seed=seed)

    def get(self, endpoint, pagina=1, por_pagina=500):
        if endpoint != "/v1/transacciones":
            return {"status": 404, "error": f"endpoint {endpoint} no existe"}
        ini = (pagina - 1) * por_pagina
        datos = self._eventos[ini:ini + por_pagina]
        return {"status": 200, "endpoint": endpoint, "pagina": pagina, "por_pagina": por_pagina,
                "total": len(self._eventos), "paginas": math.ceil(len(self._eventos) / por_pagina),
                "datos": json.loads(json.dumps(datos))}


def descargar_todo(api, endpoint="/v1/transacciones", por_pagina=500):
    """Recorre todas las páginas del endpoint y devuelve la lista completa de eventos."""
    primera = api.get(endpoint, pagina=1, por_pagina=por_pagina)
    eventos = list(primera["datos"])
    for p in range(2, primera["paginas"] + 1):
        eventos += api.get(endpoint, pagina=p, por_pagina=por_pagina)["datos"]
    print(f"Descargados {len(eventos)} eventos en {primera['paginas']} páginas de {endpoint}")
    return eventos


# ---------------------------------------------------------------------------
# 2. EDA automático
# ---------------------------------------------------------------------------
def eda_rapido(df, objetivo=None, id_col=None):
    """Diagnóstico de calidad: dimensiones, tipos, nulos, duplicados, negativos y tasa del objetivo."""
    print(f"Filas: {len(df):,} · Columnas: {df.shape[1]}")
    if id_col:
        print(f"IDs duplicados ({id_col}): {df[id_col].duplicated().sum()}")
    num = df.select_dtypes("number")
    tabla = pd.DataFrame({
        "tipo": df.dtypes.astype(str),
        "nulos": df.isna().sum(),
        "% nulos": (df.isna().mean() * 100).round(2),
        "valores_unicos": df.nunique(),
        "negativos": pd.Series({c: int((num[c] < 0).sum()) for c in num.columns}),
        "minimo": num.min().round(2), "mediana": num.median().round(2), "maximo": num.max().round(2),
    }).fillna("")
    if objetivo:
        print(f"Tasa de '{objetivo}': {df[objetivo].mean():.2%}")
    return tabla


# ---------------------------------------------------------------------------
# 3. Registro y checkpoints
# ---------------------------------------------------------------------------
ESTUDIANTE = None
_OK = set()
_K = "m6c"
# valores esperados (codificados) y pistas por clase
_E = "eyIxIjogWzEsIDAuMDg0NDQsIDAuMDAwNl0sICIyIjogWzEsIDAuNjc0NSwgMC4wMV0sICIzIjogWzEsIDM3LjAsIDAuMV0sICI0IjogWzEsIDAuODI4OTUsIDAuMDE1XSwgIjUiOiBbMSwgNjIuMTEyLCAwLjZdLCAiNiI6IFsxLCAwLjg2NTYsIDAuMDE1XX0="
_PISTAS = {
    "1": "La tasa de fraude es el PROMEDIO de la columna 0/1 'fraude' del DataFrame LIMPIO.",
    "2": "¿Pusiste StandardScaler() antes del KNN dentro del Pipeline y n_neighbors=5? Se mide exactitud BALANCEADA con X_test.",
    "3": "k_mejor debe salir de la lista ks en la posición del MAYOR puntaje: ks[np.argmax(puntajes)].",
    "4": "Usa kernel='rbf' con class_weight='balanced' y datos escalados (Pipeline). Mide recall con y_test.",
    "5": "KernelRidge(kernel='rbf', alpha=1.0, gamma=0.1) sobre Xr escalado; el RMSE se mide en dólares.",
    "6": "Usa ccp_alpha=alpha_mejor, class_weight='balanced' y random_state=42; mide la exactitud BALANCEADA con X_test.",
}


def _codigo(n):
    h = hashlib.sha256(f"{ESTUDIANTE.strip().lower()}|{n}|{_K}".encode()).hexdigest()[:4].upper()
    return f"K{n}-{h}"


def registrar(nombre):
    """Registra al estudiante (Checkpoint 0). Escriba 'Apellido Nombre'."""
    global ESTUDIANTE
    if not isinstance(nombre, str) or len(nombre.strip()) < 5 or "___" in nombre or "Apellido" in nombre:
        print("❌ Checkpoint 0: escriba su nombre real, por ejemplo 'Pérez Juan'.")
        return
    ESTUDIANTE = nombre.strip()
    _OK.add(0)
    print(f"Estudiante registrado: {ESTUDIANTE}")
    print(f"✅ Checkpoint 0 correcto · código {_codigo(0)}")


def checkpoint(n, valor):
    """Valida el resultado del checkpoint n e imprime un código personal si es correcto."""
    if ESTUDIANTE is None:
        print("❌ Primero registre su nombre en el Checkpoint 0 (registrar('Apellido Nombre')).")
        return
    esp = json.loads(base64.b64decode(_E))
    tipo, val, tol = esp[str(n)]
    try:
        v = float(valor)
    except Exception:
        print(f"❌ Checkpoint {n}: el resultado no es un número. ¿Completó todos los ___?")
        return
    if abs(v - val) <= tol:
        _OK.add(n)
        print(f"✅ Checkpoint {n} correcto · código {_codigo(n)}")
    else:
        print(f"❌ Checkpoint {n}: su resultado ({v:.4f}) no coincide. Pista: {_PISTAS[str(n)]}")


def resumen(total=7):
    """Muestra el avance de la clase y recuerda guardar en GitHub."""
    faltan = [i for i in range(total) if i not in _OK]
    print(f"Estudiante: {ESTUDIANTE} · checkpoints correctos: {len(_OK)}/{total}")
    print("Pendientes: " + (", ".join(map(str, faltan)) if faltan else "ninguno ✅"))
    print("👉 Responda las preguntas 💬 y guarde: Archivo → Guardar (Ctrl+S) (hasta las 22:30).")
