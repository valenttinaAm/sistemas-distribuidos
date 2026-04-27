from fastapi import FastAPI
import redis
import httpx
import json
import time
import os
import asyncio

app = FastAPI()

#redis queda como servicio separado por eso tomamos host y puerto desde variables
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

GENERADOR_URL = os.getenv("GENERADOR_URL", "http://localhost:8001")
TTL_SEGUNDOS = int(os.getenv("TTL_SEGUNDOS", 60))

#ordenamos los parametros para que la misma consulta siempre genere la misma clave
def generar_clave(tipo: str, zona_id: str, params: dict) -> str:
    params_str = ":".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{tipo}:{zona_id}:{params_str}"

async def consultar_generador(endpoint: str) -> dict:
    url = f"{GENERADOR_URL}{endpoint}"

    async with httpx.AsyncClient() as client:
        for intento in range(5):
            try:
                respuesta = await client.get(url, timeout=30)
                respuesta.raise_for_status()
                return respuesta.json()
            except httpx.ConnectError:
                if intento == 4:
                    raise
                await asyncio.sleep(1)
            except httpx.HTTPStatusError:
                raise

@app.get("/consulta/q1/{zona_id}")
async def consulta_q1(zona_id: str, confidence_min: float = 0.0):
    clave = generar_clave("count", zona_id, {"conf": confidence_min})
    return await procesar_consulta(clave, f"/q1/{zona_id}?confidence_min={confidence_min}")

@app.get("/consulta/q2/{zona_id}")
async def consulta_q2(zona_id: str, confidence_min: float = 0.0):
    clave = generar_clave("area", zona_id, {"conf": confidence_min})
    return await procesar_consulta(clave, f"/q2/{zona_id}?confidence_min={confidence_min}")

@app.get("/consulta/q3/{zona_id}")
async def consulta_q3(zona_id: str, confidence_min: float = 0.0):
    clave = generar_clave("density", zona_id, {"conf": confidence_min})
    return await procesar_consulta(clave, f"/q3/{zona_id}?confidence_min={confidence_min}")

@app.get("/consulta/q4/{zona_a}/{zona_b}")
async def consulta_q4(zona_a: str, zona_b: str, confidence_min: float = 0.0):
    clave = generar_clave("compare", f"{zona_a}:{zona_b}", {"conf": confidence_min})
    return await procesar_consulta(clave, f"/q4/{zona_a}/{zona_b}?confidence_min={confidence_min}")

@app.get("/consulta/q5/{zona_id}")
async def consulta_q5(zona_id: str, bins: int = 5):
    clave = generar_clave("confidence_dist", zona_id, {"bins": bins})
    return await procesar_consulta(clave, f"/q5/{zona_id}?bins={bins}")

async def procesar_consulta(clave: str, endpoint: str) -> dict:
    inicio = time.time()

    #si esta en redis, evitamos llamar al generador de respuestas
    valor_cache = redis_client.get(clave)
    if valor_cache:
        latencia = time.time() - inicio
        return {
            "resultado": json.loads(valor_cache),
            "cache_hit": True,
            "latencia_ms": round(latencia * 1000, 2),
            "clave": clave
        }

    #en caso de miss pedimos la respuesta al servicio correspondiente
    resultado = await consultar_generador(endpoint)
    latencia = time.time() - inicio

    #guardamos el resultado con TTL para controlar cuanto dura en cache
    redis_client.setex(clave, TTL_SEGUNDOS, json.dumps(resultado))

    return {
        "resultado": resultado,
        "cache_hit": False,
        "latencia_ms": round(latencia * 1000, 2),
        "clave": clave
    }

@app.get("/salud")
def salud():
    try:
        redis_client.ping()
        return {"estado": "ok", "redis": "conectado"}
    except:
        return {"estado": "error", "redis": "desconectado"}