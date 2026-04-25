from fastapi import FastAPI
import pandas as pd
import numpy as np
import os

app = FastAPI()

#definimos zonas manualmente para que coincidan con el generador de trafico
ZONAS = {
    "Z1": {"lat_min": -33.445, "lat_max": -33.420, "lon_min": -70.640, "lon_max": -70.600, "nombre": "Providencia"},
    "Z2": {"lat_min": -33.420, "lat_max": -33.390, "lon_min": -70.600, "lon_max": -70.550, "nombre": "Las Condes"},
    "Z3": {"lat_min": -33.530, "lat_max": -33.490, "lon_min": -70.790, "lon_max": -70.740, "nombre": "Maipú"},
    "Z4": {"lat_min": -33.460, "lat_max": -33.430, "lon_min": -70.670, "lon_max": -70.630, "nombre": "Santiago Centro"},
    "Z5": {"lat_min": -33.470, "lat_max": -33.430, "lon_min": -70.810, "lon_max": -70.760, "nombre": "Pudahuel"},
}

#aproximamos el area de cada zona en km² (conversión simple de grados → km)
def calcular_area_km2(zona):
def calcular_area_km2(zona):
    lat_diff = abs(zona["lat_max"] - zona["lat_min"]) * 111
    lon_diff = abs(zona["lon_max"] - zona["lon_min"]) * 111 * np.cos(np.radians((zona["lat_min"] + zona["lat_max"]) / 2))
    return lat_diff * lon_diff

AREAS_KM2 = {zona_id: calcular_area_km2(z) for zona_id, z in ZONAS.items()}

#guardamos los datos ya filtrados por zona para no recalcular en cada request
datos_por_zona = {}

def cargar_datos():
    ruta = "/app/datos/edificios.csv"
    #si no hay dataset generamos datos para poder probar igual el sistema

    if not os.path.exists(ruta):
        print("ADVERTENCIA: dataset no encontrado, generando datos sintéticos")
        generar_datos_sinteticos()
        return
    df = pd.read_csv(ruta)
    #separamos el dataset por zonas una vez al inicio

    for zona_id, zona in ZONAS.items():
        filtro = (
            (df["latitude"] >= zona["lat_min"]) & (df["latitude"] <= zona["lat_max"]) &
            (df["longitude"] >= zona["lon_min"]) & (df["longitude"] <= zona["lon_max"])
        )
        datos_por_zona[zona_id] = df[filtro][["latitude", "longitude", "area_in_meters", "confidence"]].to_dict("records")
        print(f"{zona_id} ({zona['nombre']}): {len(datos_por_zona[zona_id])} edificios cargados")

def generar_datos_sinteticos():
    np.random.seed(42)
    for zona_id, zona in ZONAS.items():
        n = np.random.randint(500, 2000)
        datos_por_zona[zona_id] = [
            {
                "latitude": np.random.uniform(zona["lat_min"], zona["lat_max"]),
                "longitude": np.random.uniform(zona["lon_min"], zona["lon_max"]),
                "area_in_meters": np.random.uniform(50, 500),
                "confidence": np.random.uniform(0.5, 1.0)
            }
            for _ in range(n)
        ]

cargar_datos()

#Q1conteo de edificios
@app.get("/q1/{zona_id}")
def q1_conteo(zona_id: str, confidence_min: float = 0.0):
    registros = datos_por_zona.get(zona_id, [])
    conteo = sum(1 for r in registros if r["confidence"] >= confidence_min)
    return {"zona": zona_id, "conteo": conteo, "confidence_min": confidence_min}

#Q2area promedio y total
@app.get("/q2/{zona_id}")
def q2_area(zona_id: str, confidence_min: float = 0.0):
    areas = [r["area_in_meters"] for r in datos_por_zona.get(zona_id, []) if r["confidence"] >= confidence_min]
    #si no hay datos devolvemos 0 para evitar errores en el calaculo
    if not areas:
        return {"zona": zona_id, "area_promedio": 0, "area_total": 0, "n": 0}
    return {"zona": zona_id, "area_promedio": np.mean(areas), "area_total": np.sum(areas), "n": len(areas)}

#Q3densidad por km²
@app.get("/q3/{zona_id}")
def q3_densidad(zona_id: str, confidence_min: float = 0.0):
    conteo = q1_conteo(zona_id, confidence_min)["conteo"]
    densidad = conteo / AREAS_KM2[zona_id]
    return {"zona": zona_id, "densidad_km2": densidad, "confidence_min": confidence_min}

#Q4comparacion entre dos zonas
@app.get("/q4/{zona_a}/{zona_b}")
def q4_comparar(zona_a: str, zona_b: str, confidence_min: float = 0.0):
    da = q3_densidad(zona_a, confidence_min)["densidad_km2"]
    db = q3_densidad(zona_b, confidence_min)["densidad_km2"]
    #devolvemos la zona con mayor densidad
    return {"zona_a": zona_a, "densidad_a": da, "zona_b": zona_b, "densidad_b": db, "ganador": zona_a if da > db else zona_b}

# Q5distribucion de confianza
@app.get("/q5/{zona_id}")
def q5_distribucion(zona_id: str, bins: int = 5):
    scores = [r["confidence"] for r in datos_por_zona.get(zona_id, [])]
    #agrupamos los valores en intervalos para ver cómo se distribuye la confianza

    conteos, bordes = np.histogram(scores, bins=bins, range=(0, 1))
    return {"zona": zona_id, "distribucion": [
        {"bucket": i, "min": bordes[i], "max": bordes[i+1], "conteo": int(conteos[i])}
        for i in range(bins)
    ]}

@app.get("/salud")
def salud():
    return {"estado": "ok", "zonas_cargadas": list(datos_por_zona.keys())}