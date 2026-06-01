from kafka import KafkaConsumer, KafkaProducer
import httpx
import json
import os
import time
import asyncio

#rafa esto toma las consultas del topico principal y las procesa usando el cache de la tarea 1 porsia no lo borri

KAFKA_SERVIDOR = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPICO_CONSULTAS = os.getenv("TOPICO_CONSULTAS", "consultas")
TOPICO_RETRY = os.getenv("TOPICO_RETRY", "consultas_retry")
TOPICO_DLQ = os.getenv("TOPICO_DLQ", "consultas_dlq")
GRUPO_CONSUMO = os.getenv("GRUPO_CONSUMO", "grupo-consultas")

CACHE_URL = os.getenv("CACHE_URL", "http://localhost:8002")
METRICAS_URL = os.getenv("METRICAS_URL", "http://localhost:8003")

MAX_REINTENTOS = int(os.getenv("MAX_REINTENTOS", 3))


def crear_consumer():
    # kafka a veces no alcanza a estar listo cuando parte docker
    for intento in range(10):
        try:
            consumer = KafkaConsumer(
                TOPICO_CONSULTAS,
                bootstrap_servers=KAFKA_SERVIDOR,
                group_id=GRUPO_CONSUMO,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8"))
            )
            print("Consumidor principal conectado a Kafka")
            return consumer
        except Exception:
            print(f"Esperando Kafka en consumer... intento {intento + 1}/10")
            time.sleep(3)

    raise Exception("No se pudo conectar el consumer principal a Kafka")


def crear_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_SERVIDOR,
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )


def enviar_a_retry_o_dlq(producer, mensaje, motivo):
    mensaje["retry_count"] = mensaje.get("retry_count", 0) + 1
    mensaje["ultimo_error"] = motivo
    mensaje["timestamp_retry"] = time.time()

    # si ya fallo muchas veces, lo dejamos en dlq
    if mensaje["retry_count"] > MAX_REINTENTOS:
        producer.send(TOPICO_DLQ, mensaje)
        print(f"Mensaje enviado a DLQ: {mensaje.get('id')}")
    else:
        producer.send(TOPICO_RETRY, mensaje)
        print(f"Mensaje enviado a retry {mensaje['retry_count']}/{MAX_REINTENTOS}: {mensaje.get('id')}")

    producer.flush()


