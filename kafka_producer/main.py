from kafka import KafkaProducer
import numpy as np
import time
import os
import random
import json
import uuid

#rafa aca ya no mandamos la consulta directo al cache como en la tarea 1 ahora la publicamos en kafka y despues la toma un consumidor porsia no modifiques 

KAFKA_SERVIDOR = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPICO_CONSULTAS = os.getenv("TOPICO_CONSULTAS", "consultas")

ZONAS = ["Z1", "Z2", "Z3", "Z4", "Z5"]
CONSULTAS = ["q1", "q2", "q3", "q4", "q5"]

TOTAL_CONSULTAS = int(os.getenv("TOTAL_CONSULTAS", 1000))
DISTRIBUCION = os.getenv("DISTRIBUCION", "zipf")
ZIPF_PARAMETRO = float(os.getenv("ZIPF_PARAMETRO", 1.5))
INTERVALO_SEGUNDOS = float(os.getenv("INTERVALO_SEGUNDOS", 0.1))


def crear_producer():
    #kafka a veces se demora en levantar con docker porsia
    for intento in range(10):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_SERVIDOR,
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
            print("Producer conectado a Kafka")
            return producer
        except Exception:
            print(f"Esperando Kafka... intento {intento + 1}/10")
            time.sleep(3)

    raise Exception("No se pudo conectar a Kafka")


def generar_zona_zipf():
    #misma idea de la tarea 1: algunas zonas aparecen mas que otras
    pesos = np.array([1 / i**ZIPF_PARAMETRO for i in range(1, len(ZONAS) + 1)])
    pesos = pesos / pesos.sum()
    return np.random.choice(ZONAS, p=pesos)


def generar_zona_uniforme():
    return random.choice(ZONAS)


def generar_zona():
    if DISTRIBUCION == "zipf":
        return generar_zona_zipf()
    return generar_zona_uniforme()

def generar_consulta():
    tipo = random.choice(CONSULTAS)
    confidence_min = round(random.choice([0.0, 0.5, 0.7, 0.9]), 1)
    zona = generar_zona()

    if tipo == "q1":
        endpoint = f"/consulta/q1/{zona}?confidence_min={confidence_min}"
    elif tipo == "q2":
        endpoint = f"/consulta/q2/{zona}?confidence_min={confidence_min}"
    elif tipo == "q3":
        endpoint = f"/consulta/q3/{zona}?confidence_min={confidence_min}"
    elif tipo == "q4":
        zona_b = random.choice([z for z in ZONAS if z != zona])
        endpoint = f"/consulta/q4/{zona}/{zona_b}?confidence_min={confidence_min}"
    else:
        bins = random.choice([5, 10])
        endpoint = f"/consulta/q5/{zona}?bins={bins}"
        
    #simular mensaje invalido
    if tipo == "q1" and ramdom.random() < 0.05:
        endpoint = "/consulta/q_invalida/ZX?confidence_min=0.0"

    return {
        "id": str(uuid.uuid4()),
        "tipo": tipo,
        "consulta": tipo.upper(),
        "zona_id": zona,
        "endpoint": endpoint,
        "retry_count": 0,
        "timestamp_creacion": time.time()
    }


def ejecutar_productor():
    print(f"Iniciando producer Kafka: {TOTAL_CONSULTAS} consultas con distribucion {DISTRIBUCION}")

    producer = crear_producer()

    for i in range(TOTAL_CONSULTAS):
        mensaje = generar_consulta()
        producer.send(TOPICO_CONSULTAS, mensaje)

        if (i + 1) % 100 == 0:
            print(f"Consultas publicadas: {i + 1}/{TOTAL_CONSULTAS}")

        time.sleep(INTERVALO_SEGUNDOS)

    producer.flush()
    producer.close()

    print("Producer terminado")


if __name__ == "__main__":
    ejecutar_productor()

