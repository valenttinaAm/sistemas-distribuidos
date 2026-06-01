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

async def registrar_metrica(cliente, evento):
    try:
        await cliente.post(f"{METRICAS_URL}/registrar", json=evento, timeout=10)
    except Exception as error:
        print(f"No se pudo registrar metrica: {error}")


async def enviar_a_retry_o_dlq(cliente, producer, mensaje, motivo):
    mensaje["retry_count"] = mensaje.get("retry_count", 0) + 1
    mensaje["ultimo_error"] = motivo
    mensaje["timestamp_retry"] = time.time()

    #si es q fallo muchas veces, lo dejamos en dlq
    if mensaje["retry_count"] > MAX_REINTENTOS:
        producer.send(TOPICO_DLQ, mensaje)
        producer.flush()

        evento_dlq = {
            "tipo": "dlq",
            "consulta": mensaje.get("consulta", ""),
            "zona_id": mensaje.get("zona_id", ""),
            "latencia_ms": 0,
            "cache_hit": False,
            "clave": "",
            "timestamp": time.time(),
            "retry_count": mensaje.get("retry_count", 0),
            "mensaje_id": mensaje.get("id", "")
        }


        await registrar_metrica(cliente, evento_dlq)
        print(f"Mensaje enviado a DLQ: {mensaje.get('id')}")
    else:
        producer.send(TOPICO_RETRY, mensaje)
        producer.flush()
        print(f"Mensaje enviado a retry {mensaje['retry_count']}/{MAX_REINTENTOS}: {mensaje.get('id')}")


async def procesar_mensaje(cliente, producer, mensaje):
    inicio = time.time()

    try:
        endpoint = mensaje["endpoint"]
        url = f"{CACHE_URL}{endpoint}"

        respuesta = await cliente.get(url, timeout=20)
        latencia_total = (time.time() - inicio) * 1000

        if respuesta.status_code != 200:
            await enviar_a_retry_o_dlq(cliente, producer, mensaje, f"http_{respuesta.status_code}")
            return

        datos = respuesta.json()

        evento = {
            "tipo": "procesada_kafka",
            "consulta": mensaje.get("consulta", ""),
            "zona_id": mensaje.get("zona_id", ""),
            "latencia_ms": datos.get("latencia_ms", latencia_total),
            "cache_hit": datos.get("cache_hit", False),
            "clave": datos.get("clave", ""),
            "timestamp": time.time(),
            "retry_count": mensaje.get("retry_count", 0),
            "mensaje_id": mensaje.get("id", "")
        }

        await registrar_metrica(cliente, evento)

        print(f"Procesada {mensaje.get('consulta')} zona {mensaje.get('zona_id')} retry {mensaje.get('retry_count', 0)}")

    except Exception as error:
       await enviar_a_retry_o_dlq(cliente, producer, mensaje, str(error))


async def ejecutar_consumidor():
    consumer = crear_consumer()
    producer = crear_producer()

    print("Consumidor principal escuchando consultas...")

    async with httpx.AsyncClient() as cliente:
        for mensaje_kafka in consumer:
            mensaje = mensaje_kafka.value
            await procesar_mensaje(cliente, producer, mensaje)


if __name__ == "__main__":
    asyncio.run(ejecutar_consumidor())


