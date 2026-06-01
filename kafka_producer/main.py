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


