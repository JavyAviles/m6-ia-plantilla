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
_PISTAS1 = {
    "1": "La tasa de fraude es el PROMEDIO de la columna 0/1 'fraude' del DataFrame LIMPIO.",
    "2": "¿Pusiste StandardScaler() antes del KNN dentro del Pipeline y n_neighbors=5? Se mide exactitud BALANCEADA con X_test.",
    "3": "k_mejor debe salir de la lista ks en la posición del MAYOR puntaje: ks[np.argmax(puntajes)].",
    "4": "Usa kernel='rbf' con class_weight='balanced' y datos escalados (Pipeline). Mide recall con y_test.",
    "5": "KernelRidge(kernel='rbf', alpha=1.0, gamma=0.1) sobre Xr escalado; el RMSE se mide en dólares.",
    "6": "Usa ccp_alpha=alpha_mejor, class_weight='balanced' y random_state=42; mide la exactitud BALANCEADA con X_test.",
}
_E2 = "eyIxIjogWzEsIDAuOTMsIDAuMDVdLCAiMiI6IFsxLCAwLjksIDAuMDVdLCAiMyI6IFsxLCAwLjg5LCAwLjA1XSwgIjQiOiBbMiwgWyJtb250byIsICJkaXNwb3NpdGl2b19udWV2byJdLCAwXSwgIjUiOiBbMSwgMC42MjQwOSwgMC4wMDFdLCAiNiI6IFsxLCAwLjAzMjg5NSwgMC4wMDA1XX0="
_PISTAS2 = {
    "1": "Use RandomForestClassifier(n_estimators=200, oob_score=True, class_weight='balanced', random_state=42) y lea rf.oob_score_.",
    "2": "XGBClassifier con learning_rate=0.05, max_depth=3, early_stopping_rounds=30; fit con eval_set=[(X_val, y_val)]. Mida exactitud BALANCEADA con X_test.",
    "3": "LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=15, class_weight='balanced', random_state=42, verbose=-1).",
    "4": "La variable con MAYOR promedio de |SHAP|: imp_shap.idxmax() (devuelve el nombre, entre comillas).",
    "5": "P(F|A) = sens·p / (sens·p + (1−esp)·(1−p)) con p = tasa de fraude, sens = 0.90, esp = 0.95.",
    "6": "Media posterior Beta: (a + fraudes) / (a + b + n) con a = 2 y b = 20.",
}
_E3 = "eyIxIjogWzEsIDAuMDMzMSwgMC4wMDNdLCAiMiI6IFsxLCAwLjE3NjY2LCAwLjAwMDVdLCAiMyI6IFsxLCAwLjk5OTUsIDAuMV0sICI0IjogWzEsIDAuMDcwNSwgMC4wMTVdLCAiNSI6IFszLCAwLCAwXSwgIjYiOiBbMSwgMC40MzUsIDAuMDNdfQ=="
_PISTAS3 = {
    "1": "Use pm.Beta('tasa', 2, 20) como prior y pm.Binomial('obs', n=n, p=tasa, observed=k); la media posterior es tr.posterior['tasa'].mean().",
    "2": "inferencia.query(['Default'], evidence={'Mora': 1}).values[1] es la probabilidad de Default = 1.",
    "3": "El coeficiente de dispositivo_nuevo es b[0]: tr_log.posterior['b'].values[..., 0].mean().",
    "4": "Tasa de Imbabura = sigmoide del intercepto de esa provincia; promedie sobre todas las muestras.",
    "5": "Use un nombre propio para su app (no 'PagoYa') y dos colores hex distintos, p. ej. '#7B2CBF', que no sean los de la plantilla.",
    "6": "Use prob_fraude(transaccion) con la transacción dada y tome el promedio: probs.mean().",
}
_CLASES = {1: (_E, _PISTAS1), 2: (_E2, _PISTAS2), 3: (_E3, _PISTAS3)}
_COLORES_PROHIBIDOS = {'#7B2CBF', '#1B2A47', '#0B5C7E', '#E0A526', '#D7262C', '#000000', '#FFFFFF', '#FF0000', '#00FF00', '#0000FF'}
CLASE = 1
X_COLS = ['edad', 'antiguedad_meses', 'ingreso_mensual', 'monto', 'hora',
          'distancia_km', 'intentos_pin', 'dispositivo_nuevo']


def cargar_pagoya_limpio(seed=2026):
    """Descarga la API PagoYa y aplica la limpieza de la Clase 1 (duplicados, montos ≤ 0, edad nula)."""
    eventos = descargar_todo(APIPagoYa(seed=seed))
    df = pd.json_normalize(eventos)
    df.columns = [c.split('.')[-1] for c in df.columns]
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hora'] = df['timestamp'].dt.hour
    df['dispositivo_nuevo'] = df['dispositivo_nuevo'].astype(int)
    df = df.drop_duplicates('evento_id').query('monto > 0').copy()
    df['edad'] = df['edad'].fillna(df['edad'].median())
    print(f"Datos limpios: {len(df)} transacciones · tasa de fraude {df['fraude'].mean():.2%}")
    return df.reset_index(drop=True)


def _codigo(n):
    h = hashlib.sha256(f"{ESTUDIANTE.strip().lower()}|{n}|{_K}".encode()).hexdigest()[:4].upper()
    return f"K{n}-{h}"


def registrar(nombre, clase=1):
    """Registra al estudiante (Checkpoint 0). Escriba 'Apellido Nombre' y el número de la clase."""
    global ESTUDIANTE, CLASE
    CLASE = int(clase)
    _OK.clear()
    if not isinstance(nombre, str) or len(nombre.strip()) < 5 or "___" in nombre or "Apellido" in nombre:
        print("❌ Checkpoint 0: escriba su nombre real, por ejemplo 'Pérez Juan'.")
        return
    ESTUDIANTE = nombre.strip()
    _OK.add(0)
    print(f"Estudiante registrado: {ESTUDIANTE}")
    print(f"Clase {CLASE}")
    print(f"✅ Checkpoint 0 correcto · código {_codigo(0)}")


def checkpoint(n, valor):
    """Valida el resultado del checkpoint n e imprime un código personal si es correcto."""
    if ESTUDIANTE is None:
        print("❌ Primero registre su nombre en el Checkpoint 0 (registrar('Apellido Nombre')).")
        return
    enc, pistas = _CLASES[CLASE]
    esp = json.loads(base64.b64decode(enc))
    tipo, val, tol = esp[str(n)]
    if tipo == 3:                                   # personalización de la app: (nombre, color1, color2)
        import re as _re
        try:
            app, c1, c2 = valor
        except Exception:
            print(f"❌ Checkpoint {n}: entregue (nombre_app, color_principal, color_alerta)."); return
        hexok = lambda c: isinstance(c, str) and _re.fullmatch(r"#[0-9A-Fa-f]{6}", c) is not None
        if (not isinstance(app, str) or len(app.strip()) < 3 or '___' in app or app.strip().lower() == 'pagoya'
                or not hexok(c1) or not hexok(c2) or c1.upper() == c2.upper()
                or c1.upper() in _COLORES_PROHIBIDOS or c2.upper() in _COLORES_PROHIBIDOS):
            print(f"❌ Checkpoint {n}: personalización no válida. Pista: {pistas[str(n)]}"); return
        _OK.add(n)
        print(f"Huella UI: {app.strip()} · {c1.upper()} · {c2.upper()}")
        print(f"✅ Checkpoint {n} correcto · código {_codigo(n)}")
        return
    if tipo == 2:                                   # respuesta de texto (nombre de variable)
        validos = [str(v).lower() for v in (val if isinstance(val, list) else [val])]
        if str(valor).strip().lower() in validos:
            _OK.add(n); print(f"✅ Checkpoint {n} correcto · código {_codigo(n)}")
        else:
            print(f"❌ Checkpoint {n}: «{valor}» no coincide. Pista: {pistas[str(n)]}")
        return
    try:
        v = float(valor)
    except Exception:
        print(f"❌ Checkpoint {n}: el resultado no es un número. ¿Completó todos los ___?")
        return
    if abs(v - val) <= tol:
        _OK.add(n)
        print(f"✅ Checkpoint {n} correcto · código {_codigo(n)}")
    else:
        print(f"❌ Checkpoint {n}: su resultado ({v:.4f}) no coincide. Pista: {pistas[str(n)]}")


def _rhat(x):
    """R-hat dividido (Gelman-Rubin) de una matriz cadenas × muestras."""
    c, n = x.shape; h = n // 2; x = np.concatenate([x[:, :h], x[:, h:2 * h]]); m, n = x.shape
    B = n * x.mean(1).var(ddof=1); W = x.var(1, ddof=1).mean()
    return float(np.sqrt(((n - 1) / n * W + B / n) / W))


def _ess(x):
    """Tamaño efectivo de muestra (autocorrelación con pares positivos de Geyer)."""
    m, n = x.shape; xc = x - x.mean(1, keepdims=True)
    acf = np.mean([np.correlate(r, r, 'full')[n - 1:] / (r.var() * n) for r in xc], axis=0)
    s, k = 0.0, 1
    while k + 1 < n:
        par = acf[k] + acf[k + 1]
        if par < 0: break
        s += par; k += 2
    return float(m * n / (1 + 2 * s))


def diagnostico(traza, variables):
    """Tabla de diagnóstico MCMC: media, desviación, intervalo creíble 94 %, R-hat y ESS."""
    filas = {}
    for v in variables:
        x = np.asarray(traza.posterior[v].values)
        x = x.reshape(x.shape[0], x.shape[1], -1)
        for j in range(x.shape[2]):
            xs = x[:, :, j]; nom = v if x.shape[2] == 1 else f"{v}[{j}]"
            filas[nom] = {'media': xs.mean(), 'desv': xs.std(), 'ic_3%': np.percentile(xs, 3), 'ic_97%': np.percentile(xs, 97),
                          'r_hat': _rhat(xs), 'ess': _ess(xs)}
    return pd.DataFrame(filas).T.round(4)


def semilla_personal(nombre):
    """Semilla única derivada del nombre del estudiante (datos personalizados del deber)."""
    return int(hashlib.sha256(nombre.strip().lower().encode()).hexdigest()[:8], 16) % 1_000_000


def datos_deber(nombre):
    """Datos PagoYa personalizados para el deber: cada estudiante obtiene transacciones distintas."""
    if not isinstance(nombre, str) or len(nombre.strip()) < 5 or '___' in nombre:
        raise ValueError("Escriba su nombre real como 'Apellido Nombre'.")
    sem = semilla_personal(nombre)
    print(f"Huella de datos: {nombre.strip()} · semilla {sem}")
    df = cargar_pagoya_limpio(seed=sem)
    df['ratio'] = df['monto'] / df['ingreso_mensual']
    return df


def _semaforo(p):
    return ('✅ APROBADA', '#2E8B57') if p < 0.2 else (('⚠️ REVISAR', '#E0A526') if p < 0.5 else ('⛔ BLOQUEADA', '#D7262C'))


def pantalla_app(nombre_app, color_principal, color_alerta, transaccion, probs):
    """Dibuja la 'pantalla del celular' de la app del estudiante con el resultado de una transacción."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    p = float(np.mean(probs)); lo, hi = np.percentile(probs, [5, 95]); txt, col = _semaforo(p)
    fig, ax = plt.subplots(figsize=(3.4, 6.2)); ax.set_xlim(0, 1); ax.set_ylim(0, 1.8); ax.axis('off')
    ax.add_patch(FancyBboxPatch((0.02, 0.02), 0.96, 1.76, boxstyle='round,pad=0.02,rounding_size=0.08', fc='#F7F7F9', ec='#333', lw=3))
    ax.add_patch(FancyBboxPatch((0.06, 1.45), 0.88, 0.25, boxstyle='round,pad=0.01,rounding_size=0.04', fc=color_principal, ec='none'))
    ax.text(0.5, 1.575, nombre_app, ha='center', va='center', color='white', fontsize=15, weight='bold')
    ax.text(0.5, 1.33, f"Pago de USD {transaccion.get('monto', 0):,.2f}", ha='center', fontsize=12, weight='bold', color='#222')
    lineas = [f"Dispositivo nuevo: {'sí' if transaccion.get('dispositivo_nuevo') else 'no'}",
              f"Distancia: {transaccion.get('distancia_km', 0):.0f} km", f"Intentos de PIN: {transaccion.get('intentos_pin', 1)}"]
    for i, l in enumerate(lineas): ax.text(0.12, 1.18 - i * 0.09, l, fontsize=10, color='#444')
    ax.add_patch(FancyBboxPatch((0.1, 0.55), 0.8, 0.3, boxstyle='round,pad=0.01,rounding_size=0.04', fc=col, ec='none'))
    ax.text(0.5, 0.70, txt, ha='center', va='center', color='white', fontsize=14, weight='bold')
    ax.text(0.5, 0.42, f"Riesgo de fraude: {p:.0%}", ha='center', fontsize=12, color=color_alerta, weight='bold')
    ax.text(0.5, 0.33, f"Intervalo creíble 90 %: {lo:.0%} – {hi:.0%}", ha='center', fontsize=9.5, color='#444')
    ax.add_patch(FancyBboxPatch((0.25, 0.1), 0.5, 0.12, boxstyle='round,pad=0.01,rounding_size=0.05', fc=color_alerta, ec='none'))
    ax.text(0.5, 0.16, 'Confirmar', ha='center', va='center', color='white', fontsize=11, weight='bold')
    plt.show()


def simulador(prob_fraude, nombre_app, color_principal, color_alerta):
    """Simulador interactivo (ipywidgets): mueva los controles y vea el riesgo de fraude con su incertidumbre."""
    import ipywidgets as w
    from IPython.display import display, HTML
    monto = w.FloatSlider(value=80, min=1, max=1500, step=1, description='Monto USD')
    ingreso = w.FloatSlider(value=900, min=200, max=4000, step=10, description='Ingreso USD')
    dist = w.FloatSlider(value=3, min=0, max=80, step=1, description='Distancia km')
    nuevo = w.Checkbox(value=False, description='Dispositivo nuevo')
    pin = w.IntSlider(value=1, min=1, max=3, description='Intentos PIN')
    salida = w.Output()
    def actualizar(*_):
        t = {'dispositivo_nuevo': int(nuevo.value), 'distancia_km': dist.value,
             'ratio': monto.value / ingreso.value, 'intentos_pin': pin.value}
        pr = prob_fraude(t); p = float(np.mean(pr)); lo, hi = np.percentile(pr, [5, 95]); txt, col = _semaforo(p)
        with salida:
            salida.clear_output()
            display(HTML(f"""<div style="font-family:Arial;width:330px;border:3px solid #333;border-radius:22px;padding:14px;background:#F7F7F9">
<div style="background:{color_principal};color:white;border-radius:12px;padding:10px;text-align:center;font-size:20px;font-weight:bold">{nombre_app}</div>
<p style="font-size:16px;margin:12px 4px"><b>Pago de USD {monto.value:,.2f}</b></p>
<div style="background:{col};color:white;border-radius:10px;padding:12px;text-align:center;font-size:18px;font-weight:bold">{txt}</div>
<p style="color:{color_alerta};font-size:16px;font-weight:bold;text-align:center">Riesgo de fraude: {p:.0%}</p>
<p style="text-align:center;font-size:13px">Intervalo creíble 90 %: {lo:.0%} – {hi:.0%}</p></div>"""))
    for c in (monto, ingreso, dist, nuevo, pin): c.observe(actualizar, names='value')
    actualizar(); display(w.HBox([w.VBox([monto, ingreso, dist, nuevo, pin]), salida]))


# ---------------------------------------------------------------------------
# 4. Proyecto final
# ---------------------------------------------------------------------------
_EMPLEO = ['dependiente', 'independiente', 'informal']


def _generar_creditos(n=2500, seed=2026):
    """Solicitudes de microcrédito de usuarios de PagoYa (simuladas). Objetivo: default (1 = impago)."""
    rng = np.random.default_rng(seed)
    edad = rng.integers(20, 66, n)
    empleo = rng.choice(_EMPLEO, n, p=[.5, .3, .2])
    ingreso = np.round(np.exp(rng.normal(6.8, .45, n)) * np.where(empleo == 'dependiente', 1.1, 0.95), 2)
    antig = rng.integers(1, 61, n)
    tx_mes = rng.poisson(14, n) + 1
    plazo = rng.choice([6, 12, 24], n, p=[.3, .5, .2])
    monto = np.round(np.clip(ingreso * rng.uniform(0.3, 2.5, n), 100, 5000), -1)
    cuota = np.round(monto * (1 + 0.015 * plazo) / plazo, 2)
    ratio_cuota = cuota / ingreso
    mora_previa = (rng.random(n) < .12).astype(int)
    z = (-3.0 + 2.2 * (ratio_cuota > .35) + 1.6 * mora_previa + 0.9 * (empleo == 'informal') + 0.8 * (antig < 6)
         - 0.03 * (tx_mes - 14) + 1.2 * mora_previa * (empleo == 'informal') - 0.012 * (edad - 40) + rng.normal(0, .3, n))
    default = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    return pd.DataFrame({'solicitud_id': [f'CR-{i:05d}' for i in range(n)], 'edad': edad, 'tipo_empleo': empleo,
                         'ingreso_mensual': ingreso, 'antiguedad_meses': antig, 'transacciones_mes': tx_mes,
                         'monto_credito': monto, 'plazo_meses': plazo, 'cuota': cuota, 'ratio_cuota': np.round(ratio_cuota, 4),
                         'mora_previa': mora_previa, 'default': default})


def _perfiles_usuarios(df):
    """Agrega las transacciones por usuario (para segmentación y anomalías)."""
    d = df.assign(noche=(df['hora'] <= 5).astype(int))
    g = d.groupby('id').agg(edad=('edad', 'first'), ingreso_mensual=('ingreso_mensual', 'first'),
                            antiguedad_meses=('antiguedad_meses', 'first'), provincia=('provincia', 'first'),
                            n_transacciones=('evento_id', 'count'), monto_medio=('monto', 'mean'), monto_max=('monto', 'max'),
                            pct_noche=('noche', 'mean'), pct_dispositivo_nuevo=('dispositivo_nuevo', 'mean'),
                            distancia_media=('distancia_km', 'mean'), intentos_medios=('intentos_pin', 'mean'),
                            fraudes=('fraude', 'sum'))
    return g.round(4).reset_index().rename(columns={'id': 'usuario_id'})


def datos_proyecto(grupo, problema):
    """Datos personalizados del proyecto. problema: 'fraude', 'credito' o 'segmentacion'."""
    if not isinstance(grupo, str) or len(grupo.strip()) < 3 or '___' in grupo:
        raise ValueError("Escriba el nombre del grupo, por ejemplo 'Grupo 3'.")
    sem = semilla_personal('proyecto|' + grupo)
    print(f"Huella de datos del proyecto: {grupo.strip()} · {problema} · semilla {sem}")
    if problema == 'fraude':
        df = cargar_pagoya_limpio(seed=sem); df['ratio'] = df['monto'] / df['ingreso_mensual']; return df
    if problema == 'credito':
        df = _generar_creditos(seed=sem)
        print(f"Solicitudes de microcrédito: {len(df)} · tasa de default {df['default'].mean():.2%}"); return df
    if problema == 'segmentacion':
        df = _perfiles_usuarios(cargar_pagoya_limpio(seed=sem))
        print(f"Perfiles de usuario: {len(df)}"); return df
    raise ValueError("problema debe ser 'fraude', 'credito' o 'segmentacion'.")


def pantalla_resultado(nombre_app, color_principal, color_alerta, titulo, lineas, probs=None, etiqueta=None):
    """Pantalla genérica de la app (proyecto): título, líneas de detalle y, si hay, riesgo con intervalo."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(3.4, 6.2)); ax.set_xlim(0, 1); ax.set_ylim(0, 1.8); ax.axis('off')
    ax.add_patch(FancyBboxPatch((0.02, 0.02), 0.96, 1.76, boxstyle='round,pad=0.02,rounding_size=0.08', fc='#F7F7F9', ec='#333', lw=3))
    ax.add_patch(FancyBboxPatch((0.06, 1.45), 0.88, 0.25, boxstyle='round,pad=0.01,rounding_size=0.04', fc=color_principal, ec='none'))
    ax.text(0.5, 1.575, nombre_app, ha='center', va='center', color='white', fontsize=15, weight='bold')
    ax.text(0.5, 1.33, titulo, ha='center', fontsize=12, weight='bold', color='#222')
    for i, l in enumerate(lineas[:5]): ax.text(0.1, 1.18 - i * 0.09, l, fontsize=9.5, color='#444')
    if probs is not None:
        p = float(np.mean(probs)); lo, hi = np.percentile(probs, [5, 95]); txt, col = _semaforo(p)
        ax.add_patch(FancyBboxPatch((0.1, 0.55), 0.8, 0.25, boxstyle='round,pad=0.01,rounding_size=0.04', fc=col, ec='none'))
        ax.text(0.5, 0.675, etiqueta or txt, ha='center', va='center', color='white', fontsize=13, weight='bold')
        ax.text(0.5, 0.42, f"Riesgo: {p:.0%}", ha='center', fontsize=12, color=color_alerta, weight='bold')
        ax.text(0.5, 0.33, f"Intervalo 90 %: {lo:.0%} – {hi:.0%}", ha='center', fontsize=9.5, color='#444')
    elif etiqueta:
        ax.add_patch(FancyBboxPatch((0.1, 0.55), 0.8, 0.25, boxstyle='round,pad=0.01,rounding_size=0.04', fc=color_alerta, ec='none'))
        ax.text(0.5, 0.675, etiqueta, ha='center', va='center', color='white', fontsize=13, weight='bold')
    plt.show()


def ficha_modelo(grupo, problema, modelo, metricas, hiperparametros, semilla=42, archivo='ficha_modelo.json'):
    """Genera ficha_modelo.json (para subir a la carpeta proyecto/ del repositorio) y la descarga en Colab."""
    import platform, datetime, sklearn
    ficha = {'grupo': grupo, 'problema': problema, 'modelo': modelo, 'metricas': metricas,
             'hiperparametros': hiperparametros, 'semilla': semilla,
             'semilla_datos': semilla_personal('proyecto|' + grupo),
             'fecha': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
             'versiones': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                           'scikit-learn': sklearn.__version__}}
    with open(archivo, 'w', encoding='utf-8') as f:
        json.dump(ficha, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(ficha, ensure_ascii=False, indent=2, default=str))
    try:
        from google.colab import files; files.download(archivo)
    except Exception:
        print(f"Archivo guardado: {archivo}")
    return ficha


def resumen(total=7):
    """Muestra el avance de la clase y recuerda guardar en GitHub."""
    faltan = [i for i in range(total) if i not in _OK]
    print(f"Estudiante: {ESTUDIANTE} · checkpoints correctos: {len(_OK)}/{total}")
    print("Pendientes: " + (", ".join(map(str, faltan)) if faltan else "ninguno ✅"))
    print("👉 Responda las preguntas 💬 y guarde: Archivo → Guardar (Ctrl+S) (hasta las 22:30).")
