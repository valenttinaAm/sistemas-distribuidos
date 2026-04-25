import httpx
import numpy as np
import asyncio
import time
import os
import random
#estas urls vienen desde docker-compose para no hardcodear direcciones
CACHE_URL = os.getenv("CACHE_URL", "http://localhost:8002")
METRICAS_URL = os.getenv("METRICAS_URL", "http://localhost:8003")

ZONAS = ["Z1", "Z2", "Z3", "Z4", "Z5"]
CONSULTAS = ["q1", "q2", "q3", "q4", "q5"]

#parametros del experimento (los cambiamos sin tocar codigo)
TOTAL_CONSULTAS = int(os.getenv("TOTAL_CONSULTAS", 1000))
DISTRIBUCION = os.getenv("DISTRIBUCION", "zipf")  
ZIPF_PARAMETRO = float(os.getenv("ZIPF_PARAMETRO", 1.5))
INTERVALO_SEGUNDOS = float(os.getenv("INTERVALO_SEGUNDOS", 0.1))

#con zipf algunas zonas se repiten mucho mas que otras(simula uso real)
def generar_zona_zipf() -> str:
    #con zipf hacemos que algunas zonas se repitan más, como pasaría en zonas de alta demanda
    pesos = np.array([1/i**ZIPF_PARAMETRO for i in range(1, len(ZONAS)+1)])
    pesos = pesos / pesos.sum()
    return np.random.choice(ZONAS, p=pesos)

def generar_zona_uniforme() -> str:
    return random.choice(ZONAS)

def generar_zona() -> str:
    if DISTRIBUCION == "zipf":
        return generar_zona_zipf()
    return generar_zona_uniforme()

#generamos consultas variadas para no sesgar el experimento
def generar_consulta() -> tuple:
    tipo = random.choice(CONSULTAS)
    confidence_min = round(random.choice([0.0, 0.5, 0.7, 0.9]), 1)
    zona = generar_zona()
    
    if tipo == "q1":
        return tipo, f"/consulta/q1/{zona}?confidence_min={confidence_min}", zona
    elif tipo == "q2":
        return tipo, f"/consulta/q2/{zona}?confidence_min={confidence_min}", zona
    elif tipo == "q3":
        return tipo, f"/consulta/q3/{zona}?confidence_min={confidence_min}", zona
    elif tipo == "q4":
        zona_b = random.choice([z for z in ZONAS if z != zona])
        return tipo, f"/consulta/q4/{zona}/{zona_b}?confidence_min={confidence_min}", zona
    elif tipo == "q5":
        bins = random.choice([5, 10])
        return tipo, f"/consulta/q5/{zona}?bins={bins}", zona

async def enviar_consulta(cliente: httpx.AsyncClient, tipo: str, endpoint: str, zona: str):
    try:
        inicio = time.time()
        respuesta = await cliente.get(f"{CACHE_URL}{endpoint}", timeout=30)
        datos = respuesta.json()
        latencia = (time.time() - inicio) * 1000

        #guardamos cada evento para analizar después hit rate y latencias
        evento = {
            "tipo": "hit" if datos.get("cache_hit") else "miss",
            "consulta": tipo.upper(),
            "zona_id": zona,
            "latencia_ms": datos.get("latencia_ms", latencia),
            "cache_hit": datos.get("cache_hit", False),
            "clave": datos.get("clave", ""),
            "timestamp": time.time()
        }
        #este delay controla la tasa de consultas (más chico = mas carga)

        await cliente.post(f"{METRICAS_URL}/registrar", json=evento, timeout=10)

    except Exception as e:
        print(f"Error en consulta {tipo} zona {zona}: {e}")

async def ejecutar_experimento():
    print(f"Iniciando experimento: {TOTAL_CONSULTAS} consultas con distribución {DISTRIBUCION}")
    inicio = time.time()

    async with httpx.AsyncClient() as cliente:
        for i in range(TOTAL_CONSULTAS):
            tipo, endpoint, zona = generar_consulta()
            await enviar_consulta(cliente, tipo, endpoint, zona)
            await asyncio.sleep(INTERVALO_SEGUNDOS)
            #mostramos progreso para no quedar a ciegas en ejecuciones largas
            if (i + 1) % 100 == 0:
                print(f"Progreso: {i+1}/{TOTAL_CONSULTAS} consultas enviadas")

    duracion = time.time() - inicio
    print(f"Experimento finalizado en {duracion:.2f} segundos")

if __name__ == "__main__":
    asyncio.run(ejecutar_experimento())