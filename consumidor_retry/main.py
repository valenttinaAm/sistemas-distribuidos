from kafka import KafkaConsumer, KafkaProducer
import httpx
import json
import os
import time
import asyncio
#este toma las consultas que fallaron y le da como otra oportunidad antes de mandarlas al dql (no le metas dedos a esto vale)

KAFKA_SERVIDOR = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPICO_RETRY = os.getenv("TOPICO_RETRY", "consultas_retry")
TOPICO_DLQ = os.getenv("TOPICO_DLQ", "consultas_dlq")
GRUPO_CONSUMO = os.getenv("GRUPO_CONSUMO", "grupo-retry")

CACHE_URL = os.getenv("CACHE_URL", "http://localhost:8002")
METRICAS_URL = os.getenv("METRICAS_URL", "http://localhost:8003")

MAX_REINTENTOS = int(os.getenv("MAX_REINTENTOS", 3))
ESPERA_RETRY_SEGUNDOS = float(os.getenv("ESPERA_RETRY_SEGUNDOS", 2))

def crear_consumer():
    # igual que el otro consumer, esperamos kafka por si docker aun esta levantando
    for intento in range(10):
        try:
            consumer = KafkaConsumer(
                TOPICO_RETRY,
                bootstrap_servers=KAFKA_SERVIDOR,
                group_id=GRUPO_CONSUMO,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8"))
            )
            print("Consumidor retry conectado a Kafka")
            return consumer
        except Exception:
            print(f"Esperando Kafka en retry... intento {intento + 1}/10")
            time.sleep(3)

    raise Exception("No se pudo conectar el consumer retry a Kafka")


def crear_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_SERVIDOR,
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )


async def registrar_metrica(cliente, evento):
    try:
        await cliente.post(f"{METRICAS_URL}/registrar", json=evento, timeout=10)
    except Exception as error:
        print(f"No se pudo registrar metrica: {error}")


def enviar_dlq(producer, mensaje, motivo):
    mensaje["ultimo_error"] = motivo
    mensaje["timestamp_dlq"] = time.time()

    producer.send(TOPICO_DLQ, mensaje)
    producer.flush()

    print(f"Mensaje enviado a DLQ: {mensaje.get('id')}")


async def procesar_retry(cliente, producer, mensaje):
    #dejamos una espera chica para simular que reintentamos despues y no altiro porsiacaso
    await asyncio.sleep(ESPERA_RETRY_SEGUNDOS)

    inicio = time.time()

    try:
        endpoint = mensaje["endpoint"]
        url = f"{CACHE_URL}{endpoint}"

        respuesta = await cliente.get(url, timeout=20)
        latencia_total = (time.time() - inicio) * 1000

        if respuesta.status_code != 200:
            mensaje["retry_count"] = mensaje.get("retry_count", 0) + 1

            if mensaje["retry_count"] > MAX_REINTENTOS:
                enviar_dlq(producer, mensaje, f"http_{respuesta.status_code}")
                return

            producer.send(TOPICO_RETRY, mensaje)
            producer.flush()
            print(f"Retry fallo otra vez, se reenvia: {mensaje.get('id')}")
            return

        datos = respuesta.json()

        evento = {
            "tipo": "recuperada_retry",
            "consulta": mensaje.get("consulta", ""),
            "zona_id": mensaje.get("zona_id", ""),
            "latencia_ms": latencia_total,
            "cache_hit": datos.get("cache_hit", False),
            "clave": datos.get("clave", ""),
            "timestamp": time.time()
        }

        await registrar_metrica(cliente, evento)

        print(f"Consulta recuperada desde retry: {mensaje.get('id')}")

    except Exception as error:
        mensaje["retry_count"] = mensaje.get("retry_count", 0) + 1

        if mensaje["retry_count"] > MAX_REINTENTOS:
            enviar_dlq(producer, mensaje, str(error))
        else:
            mensaje["ultimo_error"] = str(error)
            mensaje["timestamp_retry"] = time.time()
            producer.send(TOPICO_RETRY, mensaje)
            producer.flush()
            print(f"Retry con error, se vuelve a mandar: {mensaje.get('id')}")


async def ejecutar_retry():
    consumer = crear_consumer()
    producer = crear_producer()

    print("Consumidor retry escuchando consultas fallidas...")

    async with httpx.AsyncClient() as cliente:
        for mensaje_kafka in consumer:
            mensaje = mensaje_kafka.value
            await procesar_retry(cliente, producer, mensaje)


if __name__ == "__main__":
    asyncio.run(ejecutar_retry())


