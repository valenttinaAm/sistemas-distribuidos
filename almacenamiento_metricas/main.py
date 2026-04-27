from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import time
import json

app = FastAPI()

# Lista en memoria donde vamos guardando los eventos que llegan desde el sistema
eventos = []

class Evento(BaseModel):
    tipo: str          
    consulta: str      
    zona_id: str
    latencia_ms: float
    cache_hit: bool
    clave: str
    timestamp: float = None


@app.post("/registrar")
def registrar_evento(evento: Evento):
#si no viene timestamp lo agregamos ac para poder calcular metricas desps
    if evento.timestamp is None:
        evento.timestamp = time.time()
    eventos.append(evento.dict())
    return {"estado": "ok"}

@app.get("/metricas")
def obtener_metricas():
    if not eventos:
        return {"mensaje": "sin eventos registrados"}
    
    df = pd.DataFrame(eventos)
    
    total = len(df)
    hits = len(df[df["cache_hit"] == True])
    misses = len(df[df["cache_hit"] == False])
    
    hit_rate = hits / total if total > 0 else 0
    miss_rate = misses / total if total > 0 else 0

#usamos el rango de tiempo total para estimar cuanta consultas por segundo procesamos
    duracion = df["timestamp"].max() - df["timestamp"].min()
    throughput = total / duracion if duracion > 0 else 0
    
    return {
        "total_consultas": total,
        "hits": hits,
        "misses": misses,
        "hit_rate": round(hit_rate, 4),
        "miss_rate": round(miss_rate, 4),
   #percentiles para ver comportamiento tipico y peor caso
        "latencia_p50_ms": round(df["latencia_ms"].quantile(0.50), 2),
        "latencia_p95_ms": round(df["latencia_ms"].quantile(0.95), 2),
        "latencia_promedio_ms": round(df["latencia_ms"].mean(), 2),
        "por_consulta": df.groupby("consulta")["cache_hit"].mean().round(4).to_dict()
    }

@app.get("/metricas/detalle")
def obtener_detalle():
    return {"eventos": eventos[-100:]}  

@app.get("/metricas/exportar")
def exportar_metricas():
    if not eventos:
        return {"mensaje": "sin eventos para exportar"}

    df = pd.DataFrame(eventos)
    df.to_csv("metricas.csv", index=False)

    return {"estado": "ok", "archivo": "metricas.csv"}


@app.delete("/metricas/limpiar")
def limpiar_metricas():
    eventos.clear()
    return {"estado": "ok", "mensaje": "métricas limpiadas"}

@app.get("/salud")
def salud():
    return {"estado": "ok", "eventos_registrados": len(eventos)}