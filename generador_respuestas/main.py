from fastapi import FastAPI, HTTPException
import pandas as pd
import numpy as np
import os

app = FastAPI()

#definimos las zonas que vamos a usar en las consultas
#esto lo dejamos fijo pra q coincida con el generador de trafico
ZONAS = {
    "Z1": {"lat_min": -33.445, "lat_max": -33.420, "lon_min": -70.640, "lon_max": -70.600, "nombre": "Providencia"},
    "Z2": {"lat_min": -33.420, "lat_max": -33.390, "lon_min": -70.600, "lon_max": -70.550, "nombre": "Las Condes"},
    "Z3": {"lat_min": -33.530, "lat_max": -33.490, "lon_min": -70.790, "lon_max": -70.740, "nombre": "Maipú"},
    "Z4": {"lat_min": -33.460, "lat_max": -33.430, "lon_min": -70.670, "lon_max": -70.630, "nombre": "Santiago Centro"},
    "Z5": {"lat_min": -33.470, "lat_max": -33.430, "lon_min": -70.810, "lon_max": -70.760, "nombre": "Pudahuel"},
}


#aca calculamos el area aproximada de cada zona
#no es exacto pero para el experimento sirve:)
def calcular_area_km2(zona: dict) -> float:
    lat_diff = abs(zona["lat_max"] - zona["lat_min"]) * 111
    lon_diff = abs(zona["lon_max"] - zona["lon_min"]) * 111 * np.cos(
        np.radians((zona["lat_min"] + zona["lat_max"]) / 2)
    )
    return float(lat_diff * lon_diff)


AREAS_KM2 = {zona_id: calcular_area_km2(zona) for zona_id, zona in ZONAS.items()}

#guardamos los datos separados por zona para no recalcular filtros todo el rato
datos_por_zona = {}


def validar_zona(zona_id: str):
    if zona_id not in ZONAS:
        raise HTTPException(status_code=404, detail=f"Zona no válida: {zona_id}")


def cargar_datos():
    ruta = "/app/datos/edificios.csv"

    #si no existe el archivo generamos datos falsos pa que el sistema no muera
    if not os.path.exists(ruta):
        print("ADVERTENCIA: dataset no encontrado, generando datos sintéticos")
        generar_datos_sinteticos()
        return

    df = pd.read_csv(ruta)

    for zona_id, zona in ZONAS.items():
        filtro = (
            (df["latitude"] >= zona["lat_min"]) & (df["latitude"] <= zona["lat_max"]) &
            (df["longitude"] >= zona["lon_min"]) & (df["longitude"] <= zona["lon_max"])
        )
        #dejamos solo lo que necesitamos
        datos_por_zona[zona_id] = df[filtro][
            ["latitude", "longitude", "area_in_meters", "confidence"]
        ].to_dict("records")

        print(f"{zona_id} ({zona['nombre']}): {len(datos_por_zona[zona_id])} edificios cargados")


def generar_datos_sinteticos():
    np.random.seed(42)
    #generamos datos random dentro de cada zona
    for zona_id, zona in ZONAS.items():
        n = np.random.randint(500, 2000)

        datos_por_zona[zona_id] = [
            {
                "latitude": float(np.random.uniform(zona["lat_min"], zona["lat_max"])),
                "longitude": float(np.random.uniform(zona["lon_min"], zona["lon_max"])),
                "area_in_meters": float(np.random.uniform(50, 500)),
                "confidence": float(np.random.uniform(0.5, 1.0)),
            }
            for _ in range(n)
        ]

#cargamos datos apenas levanta el servicio
cargar_datos()


@app.get("/q1/{zona_id}")
def q1_conteo(zona_id: str, confidence_min: float = 0.0):
    validar_zona(zona_id)

    registros = datos_por_zona.get(zona_id, [])
    conteo = sum(1 for r in registros if float(r["confidence"]) >= confidence_min)

    return {
        "zona": zona_id,
        "conteo": int(conteo),
        "confidence_min": float(confidence_min),
    }


@app.get("/q2/{zona_id}")
def q2_area(zona_id: str, confidence_min: float = 0.0):
    validar_zona(zona_id)

    areas = [
        float(r["area_in_meters"])
        for r in datos_por_zona.get(zona_id, [])
        if float(r["confidence"]) >= confidence_min
    ]

    if not areas:
        return {
            "zona": zona_id,
            "area_promedio": 0.0,
            "area_total": 0.0,
            "n": 0,
            "confidence_min": float(confidence_min),
        }

    return {
        "zona": zona_id,
        "area_promedio": float(np.mean(areas)),
        "area_total": float(np.sum(areas)),
        "n": int(len(areas)),
        "confidence_min": float(confidence_min),
    }


@app.get("/q3/{zona_id}")
def q3_densidad(zona_id: str, confidence_min: float = 0.0):
    validar_zona(zona_id)

    area = AREAS_KM2.get(zona_id, 0.0)

    if area <= 0:
        raise HTTPException(status_code=500, detail=f"Área inválida para zona {zona_id}")
    #reutilizamos q1 pa no repetir logica
    conteo = q1_conteo(zona_id, confidence_min)["conteo"]
    densidad = conteo / area

    return {
        "zona": zona_id,
        "densidad_km2": float(densidad),
        "confidence_min": float(confidence_min),
    }


@app.get("/q4/{zona_a}/{zona_b}")
def q4_comparar(zona_a: str, zona_b: str, confidence_min: float = 0.0):
    validar_zona(zona_a)
    validar_zona(zona_b)

    da = q3_densidad(zona_a, confidence_min)["densidad_km2"]
    db = q3_densidad(zona_b, confidence_min)["densidad_km2"]

    return {
        "zona_a": zona_a,
        "densidad_a": float(da),
        "zona_b": zona_b,
        "densidad_b": float(db),
        "ganador": zona_a if da > db else zona_b,
        "confidence_min": float(confidence_min),
    }


@app.get("/q5/{zona_id}")
def q5_distribucion(zona_id: str, bins: int = 5):
    validar_zona(zona_id)

    if bins <= 0:
        raise HTTPException(status_code=400, detail="El número de bins debe ser mayor que 0")

    scores = [float(r["confidence"]) for r in datos_por_zona.get(zona_id, [])]
    #armamos una especie de histograma pa ver como se distribuye el confidence
    conteos, bordes = np.histogram(scores, bins=bins, range=(0, 1))

    distribucion = [
        {
            "bucket": int(i),
            "min": float(bordes[i]),
            "max": float(bordes[i + 1]),
            "conteo": int(conteos[i]),
        }
        for i in range(bins)
    ]

    return {
        "zona": zona_id,
        "distribucion": distribucion,
        "bins": int(bins),
    }


@app.get("/salud")
def salud():
    return {
        "estado": "ok",
        "zonas_cargadas": list(datos_por_zona.keys()),
        "areas_km2": AREAS_KM2,
    }
