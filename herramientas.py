"""La herramienta del agente: consulta un dato del Observatorio.

Solo lee. La variable debe estar en la lista y las horas entre 1 y 72, así
que el modelo nunca escribe SQL.
"""
import json, os, sqlite3
from datetime import datetime, timedelta, timezone

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos_curso.sqlite")

# variable -> (nodo que la mide, unidad)
VARIABLES = {
    "eco2_ppm": ("aire-01", "ppm"), "tvoc_ppb": ("aire-01", "ppb"), "aqi": ("aire-01", "1 a 5"),
    "temp_c": ("clima-01", "°C"), "rh_pct": ("clima-01", "%"), "pres_hpa": ("clima-01", "hPa"),
    "luz": ("clima-01", "lux"), "suelo_pct": ("planta-01", "%"),
}
# temp_c y rh_pct también las mide aire-01: pídelas con nodo="aire-01"


def dame_lectura(variable: str, horas: int = 1, nodo: str = "") -> dict:
    """Resumen de una variable en las últimas `horas`. Devuelve un dict para el modelo."""
    if variable not in VARIABLES:
        return {"error": f"variable no permitida: {variable}", "permitidas": sorted(VARIABLES)}
    if not isinstance(horas, int) or not 1 <= horas <= 72:
        return {"error": "horas debe ser un entero entre 1 y 72"}
    nodo = nodo or VARIABLES[variable][0]
    if nodo not in ("aire-01", "clima-01", "planta-01"):
        return {"error": f"nodo no permitido: {nodo}"}

    desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    filas = con.execute("SELECT ts, v, fw FROM lecturas WHERE nodo = ? AND ts >= ? ORDER BY ts",
                        (nodo, desde)).fetchall()
    con.close()

    valores = [(ts, json.loads(v)[variable], fw) for ts, v, fw in filas if variable in json.loads(v)]
    if not valores:
        return {"error": f"sin datos de {variable} en {nodo} en las últimas {horas} h"}
    nums = [x for _, x, _ in valores]
    return {
        "variable": variable, "nodo": nodo, "unidad": VARIABLES[variable][1],
        "horas": horas, "lecturas": len(nums),
        "ultimo": nums[-1], "ts_ultimo": valores[-1][0],
        "minimo": min(nums), "maximo": max(nums), "promedio": round(sum(nums) / len(nums), 1),
        "primero": nums[0],
        "datos": "simulados" if valores[-1][2] == "simulado" else "reales",
    }


if __name__ == "__main__":
    print(dame_lectura("eco2_ppm", 3))
