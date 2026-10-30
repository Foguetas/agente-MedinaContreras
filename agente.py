"""Tu primer agente: el modelo decide, tu código ejecuta.

Ciclo: el modelo responde en JSON -> si pide consultar, corres la herramienta
-> le devuelves el resultado -> repite hasta que responda.

Correr:  python agente.py "¿Debo abrir las ventanas?"
Camino:  CAMINO=ollama (por defecto) o CAMINO=gemini con GEMINI_API_KEY
"""
import json, os, sys
from typing import Literal, Optional

from pydantic import BaseModel

from herramientas import dame_lectura

# ---- 1. Tu decisión y las variables que puede consultar -------------------
DECISION = "B"   # A ventilar el salón, B alertar de una tormenta, C regar el terrario
DECISIONES = {
    "A": ("ventilar el salón", {"eco2_ppm", "tvoc_ppb", "aqi", "temp_c", "rh_pct"}),
    "B": ("alertar de una tormenta", {"pres_hpa", "temp_c", "rh_pct"}),
    "C": ("regar el terrario", {"suelo_pct", "luz"}),
}
OBJETIVO, PERMITIDAS = DECISIONES[DECISION]
MAX_PASOS = 4

# ---- 2. El formato que debe tener cada respuesta del modelo ---------------
class Paso(BaseModel):
    accion: Literal["consultar", "responder"]
    variable: Optional[str] = None   # si consulta
    horas: Optional[int] = None      # si consulta
    texto: Optional[str] = None      # si responde
    accion_propuesta: Optional[str] = None  # algo que haría una persona, si hace falta

SISTEMA = f"""Eres un asistente del Observatorio de Ocotlán. Tu trabajo es ayudar a {OBJETIVO}.
Respondes SIEMPRE con un JSON de este formato:
  {{"accion": "consultar", "variable": "<nombre>", "horas": <1 a 72>}}   para pedir un dato
  {{"accion": "responder", "texto": "<respuesta>", "accion_propuesta": "<opcional>"}}   para contestar
Variables que puedes consultar: {", ".join(sorted(PERMITIDAS))}.
Nunca inventes una lectura: si necesitas un dato, consúltalo.
Si no sabes o no tienes datos, responde que no sabes.
Tú solo propones acciones; una persona decide si se hacen."""

# ---- 3. Las llamadas al modelo (elige tu camino) ---------------------------
CAMINO = os.environ.get("CAMINO", "ollama")
MODELO = os.environ.get("MODELO", "llama3.2:3b" if CAMINO == "ollama" else "gemini-3.5-flash-lite")

def llamar_modelo(mensajes):
    if CAMINO == "ollama":
        import ollama
        r = ollama.chat(model=MODELO, messages=mensajes, format=Paso.model_json_schema())
        return r.message.content
    from google import genai
    from google.genai import types
    contenido = [types.Content(role="model" if m["role"] == "assistant" else "user",
                               parts=[types.Part(text=m["content"])])
                 for m in mensajes if m["role"] != "system"]
    # Con el WITH lo que hago es hacer que la peticion siga viva hasta que gemini responda
    # y la cierra al terminar
    with genai.Client() as cliente:
        r = cliente.models.generate_content(
            model=MODELO, contents=contenido,
            config=types.GenerateContentConfig(system_instruction=mensajes[0]["content"],
                                            response_mime_type="application/json",
                                            response_schema=Paso))
        return r.text

# ---- 4. Reglas de seguridad ------------------------------------------------
def regla_variable(paso):
    """Regla 1: solo se consultan las variables de tu decisión."""
    return paso.variable in PERMITIDAS

def regla_aprobacion(propuesta):
    """Regla 2: ninguna acción ocurre sin que una persona la apruebe."""
    return input(f"  El agente propone: {propuesta}\n  ¿La apruebas? (s/n) ").strip().lower() == "s"
    

# Agrega aquí una o dos reglas tuyas y pruébalas.

# Regla de origen: Los datos estan clasificados como reales?
def regla_origen(resultado):
    return resultado.get("datos") == "reales"

# Regla de horas: Valida las horas que se le piden analizar al agente con un limite de 1 a 72
def regla_horas(paso):
    return paso.horas is not None and 1 <= paso.horas <= 72

# ---- 5. El ciclo del agente ------------------------------------------------
def agente(pregunta):
    mensajes = [{"role": "system", "content": SISTEMA}, {"role": "user", "content": pregunta}]
    for n in range(1, MAX_PASOS + 1):
        crudo = llamar_modelo(mensajes)
        print(f"\n[paso {n}] el modelo dijo: {crudo}")
        try:
            paso = Paso.model_validate_json(crudo)
        except Exception as e:
            mensajes += [{"role": "assistant", "content": crudo},
                         {"role": "user", "content": f"Tu respuesta no cumple el formato JSON: {e}"}]
            continue

        if paso.accion == "responder":
            print(f"\nRespuesta: {paso.texto}")
            if paso.accion_propuesta:
                ok = regla_aprobacion(paso.accion_propuesta)
                print("  -> aprobada, una persona la ejecuta" if ok else "  -> no aprobada, no se hace nada")
            return paso.texto

        if not regla_variable(paso):
            print(f"  regla 1: bloqueé la consulta de '{paso.variable}'")
            resultado = {"error": f"no puedes consultar {paso.variable}", "permitidas": sorted(PERMITIDAS)}
        elif not regla_horas(paso):
            print(" Bloquee la consulta: horas fuera del rango")
            resultado = {"error": "Debes indicar horas entre 1 y 72"}    
        else:
            resultado = dame_lectura(paso.variable, paso.horas or 1)
            print(f"  la herramienta devolvió: {resultado}")
        mensajes += [{"role": "assistant", "content": crudo},
                     {"role": "user", "content": "Resultado de la herramienta: " + json.dumps(resultado, ensure_ascii=False)}]

    print("\nLlegué al máximo de pasos sin una respuesta.")

if __name__ == "__main__":
    agente(" ".join(sys.argv[1:]) or "¿Cómo está el salón ahora?")
