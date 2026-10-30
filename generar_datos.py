"""Crea datos_curso.sqlite con datos de EJEMPLO del Observatorio.

Tiene el mismo formato que la copia nocturna real, así que tu agente
funciona igual cuando cambies este archivo por el verdadero.
Todas las filas llevan fw = 'simulado': no son mediciones.
"""
import json, math, random, sqlite3
from datetime import datetime, timedelta, timezone

random.seed(29)
FIN = datetime.now(timezone.utc).replace(second=0, microsecond=0)
INICIO = FIN - timedelta(days=7)
PASO = timedelta(minutes=5)

db = sqlite3.connect("datos_curso.sqlite")
db.executescript("""
DROP TABLE IF EXISTS lecturas; DROP TABLE IF EXISTS estado; DROP TABLE IF EXISTS referencia;
CREATE TABLE lecturas (id, ts, nodo, fw, v, raro);
CREATE TABLE estado (id, ts, nodo, rssi, uptime_s, heap_b);
CREATE TABLE referencia (id, ts, fuente, variable, valor);
""")


def hora_local(t):
    return (t.hour - 6) % 24 + t.minute / 60  # México, UTC-6


def clase(h):  # 1 si el salón está ocupado
    return 1 if 8 <= h < 15 else 0


filas, estados, n = [], [], 0
t = INICIO
while t <= FIN:
    h = hora_local(t)
    dia = (t - INICIO).total_seconds() / 86400
    ts = t.isoformat()
    # Aire: el CO2 sube con gente en el salón
    co2 = 450 + 900 * clase(h) * min(1, (h - 8) / 3 if h < 11 else 1) + random.gauss(0, 30)
    filas.append(("aire-01", {"eco2_ppm": round(co2), "tvoc_ppb": round(60 + co2 / 20 + random.gauss(0, 8)),
                              "aqi": 1 if co2 < 800 else 2 if co2 < 1200 else 3,
                              "temp_c": round(22 + 3 * clase(h) + random.gauss(0, .3), 1),
                              "rh_pct": round(55 - 6 * clase(h) + random.gauss(0, 1), 1)}, ts))
    # Clima: presión ~840 hPa (1,500 m); el último día cae como antes de una tormenta
    caida = max(0, dia - 5.8) * 14
    filas.append(("clima-01", {"temp_c": round(24 + 5 * math.sin((h - 9) / 24 * 2 * math.pi) + random.gauss(0, .3), 1),
                               "rh_pct": round(50 - 15 * math.sin((h - 9) / 24 * 2 * math.pi) + random.gauss(0, 1), 1),
                               "pres_hpa": round(842 - caida + random.gauss(0, .3), 1),
                               "luz": round(max(0, 900 * math.sin((h - 6) / 12 * math.pi)) if 6 <= h <= 18 else 0)}, ts))
    # Planta: el suelo se seca y se riega cada 3 días
    suelo = 75 - 8 * ((dia % 3)) + random.gauss(0, .5)
    filas.append(("planta-01", {"suelo_pct": round(max(5, suelo), 1),
                                "luz": round(max(0, 400 * math.sin((h - 6) / 12 * math.pi)) if 6 <= h <= 18 else 0)}, ts))
    for nodo in ("aire-01", "clima-01", "planta-01", "testigo-01"):
        estados.append((nodo, ts, random.randint(-72, -55), int((t - INICIO).total_seconds()), 180000))
    t += PASO

for nodo, v, ts in filas:
    n += 1
    db.execute("INSERT INTO lecturas VALUES (?,?,?,?,?,?)", (n, ts, nodo, "simulado", json.dumps(v), 0))
for i, (nodo, ts, rssi, up, heap) in enumerate(estados, 1):
    db.execute("INSERT INTO estado VALUES (?,?,?,?,?,?)", (i, ts, nodo, rssi, up, heap))
db.commit()
print(f"datos_curso.sqlite listo: {n} lecturas simuladas de {INICIO:%d %b} a {FIN:%d %b}")
