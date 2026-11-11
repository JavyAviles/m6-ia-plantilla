"""
verificador.py — Revisión automática del repositorio del Módulo 6 (CEC-EPN).
Se ejecuta solo en GitHub Actions cada vez que se guarda algo en el repositorio.
No califica: informa el AVANCE (checkpoints ✅, preguntas respondidas, archivos del deber y del proyecto)
y la HORA de cada guardado frente a su plazo. La calificación la hace el docente.
"""
import glob, hashlib, json, os, re, subprocess
from datetime import datetime, timezone, timedelta

EC = timezone(timedelta(hours=-5))      # hora de Ecuador
PLAZOS = {                              # entrega → fecha y hora límite (Ecuador)
    "clase1": "2026-11-11 22:30", "clase2": "2026-11-12 22:30", "clase3": "2026-11-13 22:30",
    "clase4": "2026-11-16 22:30", "clase5": "2026-11-17 22:30", "clase6": "2026-11-18 22:30",
    "deber": "2026-11-15 11:00", "proyecto": "2026-11-19 18:00",
}
PROYECTO = ["proyecto.ipynb", "README.md", "ficha_modelo.json", "presentacion.pdf"]
_K = "m6c"


def hora_commit(ruta):
    """Hora (Ecuador) del último commit que modificó el archivo."""
    try:
        iso = subprocess.check_output(["git", "log", "-1", "--format=%cI", "--", ruta], text=True).strip()
        return datetime.fromisoformat(iso).astimezone(EC) if iso else None
    except Exception:
        return None


def estado_plazo(clave, cuando):
    if cuando is None:
        return "—"
    limite = datetime.strptime(PLAZOS[clave], "%Y-%m-%d %H:%M").replace(tzinfo=EC)
    txt = cuando.strftime("%d-%m %H:%M")
    if cuando <= limite:
        return f"{txt} ✅ a tiempo"
    if clave.startswith("clase") and cuando <= limite + timedelta(days=1):
        return f"{txt} ⏳ tardío: se califica sobre 70"
    return f"{txt} ⚠️ fuera de plazo ({PLAZOS[clave]}); solo con falta justificada"


def codigo(nombre, n):
    return f"K{n}-" + hashlib.sha256(f"{nombre.strip().lower()}|{n}|{_K}".encode()).hexdigest()[:4].upper()


def revisar_clase(ruta):
    nb = json.load(open(ruta, encoding="utf-8"))
    celdas = nb.get("cells", [])
    fuente = lambda c: "".join(c.get("source", []))
    salidas = lambda c: "".join("".join(o.get("text", [])) for o in c.get("outputs", []))
    meta = re.search(r"m6:clase=(\d+);checkpoints=(\d+);preguntas=(\d+)", fuente(celdas[0]) if celdas else "")
    total_cp, total_p = (int(meta.group(2)), int(meta.group(3))) if meta else (0, 0)
    todo = "\n".join(salidas(c) for c in celdas if c.get("cell_type") == "code")
    m = re.search(r"Estudiante registrado: (.+)", todo)
    nombre = m.group(1).strip() if m else None
    validos = set()
    for n, cod in re.findall(r"✅ Checkpoint (\d+) correcto · código (K\d+-[0-9A-F]{4})", todo):
        if nombre and cod == codigo(nombre, int(n)):
            validos.add(int(n))
    resp = 0
    for c in celdas:
        if c.get("cell_type") == "markdown" and fuente(c).lstrip().startswith("### 💬 Pregunta") and "**Respuesta:**" in fuente(c):
            r = fuente(c).split("**Respuesta:**")[-1].strip()
            if len(r) > 15 and r != "___":
                resp += 1
    return nombre, validos, total_cp, resp, total_p


def main():
    filas, avisos = [], []
    for ruta in sorted(glob.glob("**/clase*.ipynb", recursive=True)):
        clave = re.search(r"(clase\d+)", os.path.basename(ruta)).group(1)
        try:
            nombre, ok, tcp, resp, tp = revisar_clase(ruta)
        except Exception as e:
            avisos.append(f"⚠️ {ruta}: no se pudo leer el cuaderno ({e}). ¿Lo guardó desde Colab?")
            continue
        if nombre is None:
            avisos.append(f"⚠️ {ruta}: falta el Checkpoint 0 (registrar su nombre).")
        filas.append((clave, ruta, nombre or "—", f"{len(ok)}/{tcp}", f"{resp}/{tp}",
                      estado_plazo(clave, hora_commit(ruta)) if clave in PLAZOS else "—"))
    deber = glob.glob("deber/*.ipynb")
    deber_txt = estado_plazo("deber", hora_commit(deber[0])) if deber else "pendiente"
    falt = [f for f in PROYECTO if not os.path.exists(os.path.join("proyecto", f))]
    proy_txt = ("completo · " + estado_plazo("proyecto", hora_commit("proyecto"))) if not falt else \
               "pendiente (faltan: " + ", ".join(falt) + ")"

    md = ["# 📋 Verificador del Módulo 6", "",
          "| Clase | Archivo | Estudiante | Checkpoints ✅ | Preguntas 💬 | Guardado (hora Ecuador) |",
          "|---|---|---|---|---|---|"]
    md += [f"| {a} | `{b}` | {c} | {d} | {e} | {f} |" for a, b, c, d, e, f in filas] or ["| — | aún no hay cuadernos de clase | | | | |"]
    md += ["", f"**Deber** (`deber/`): {deber_txt}", "", f"**Proyecto** (`proyecto/`): {proy_txt}", ""]
    md += avisos
    md += ["", "> El verificador informa su avance; la calificación la realiza el docente con la versión guardada antes de cada plazo."]
    texto = "\n".join(md)
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto + "\n")


if __name__ == "__main__":
    main()
