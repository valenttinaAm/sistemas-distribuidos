from kafka import KafkaConsumer, KafkaProducer
import httpx
import json
import os
import time

#raf esto lee las consultas del principal y las mando al cache porsia no cambies nda

KAFKA_SERVIDOR = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPICO_CONSULTAS = os.getenv("TOPICO_CONSULTAS", "consultas")
TOPICO_RETRY = os.getenv("TOPICO_RETRY", "consultas_retry")
TOPICO_DLQ = os.getenv("TOPICO_DLQ", "consultas_dlq")
GRUPO_CONSUMO = os.getenv("GRUPO_CONSUMO", "grupo-consultas")

CACHE_URL = os.getenv("CACHE_URL", "http://localhost:8002")
METRICAS_URL = os.getenv("METRICAS_URL", "http://localhost:8003")

MAX_REINTENTOS = int(os.getenv("MAX_REINTENTOS", 3))

def crear_consumer():
    #kafka puede demorarse en partir cuando docker levanta todo junto
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
            print("Consumidor conectado a Kafka")
            return consumer
        except Exception:
            print(f"Esperando Kafka para consumidor... intento {intento + 1}/10")
            time.sleep(3)

    raise Exception("No se pudo conectar el consumidor a Kafka")


def crear_producer():
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_SERVIDOR,
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )
    return producer


def mandar_a_retry(producer, mensaje, motivo):
    mensaje["retry_count"] = mensaje.get("retry_count", 0) + 1
    mensaje["ultimo_error"] = motivo
    mensaje["timestamp_retry"] = time.time()

    if mensaje["retry_count"] > MAX_REINTENTOS:
        producer.send(TOPICO_DLQ, mensaje)
        print(f"Mensaje enviado a DLQ: {mensaje.get('id')}")
    else:
        producer.send(TOPICO_RETRY, mensaje)
        print(f"Mensaje enviado a retry {mensaje['retry_count']}/{MAX_REINTENTOS}: {mensaje.get('id')}")

    producer.flush()


async def procesar_mensaje(cliente, producer, mensaje):
    inicio = time.time()

    try:
        endpoint = mensaje["endpoint"]
        url = f"{CACHE_URL}{endpoint}"

        respuesta = await cliente.get(url, timeout=20)
        latencia_total = (time.time() - inicio) * 1000

        if respuesta.status_code != 200:
            mandar_a_retry(producer, mensaje, f"http_{respuesta.status_code}")
            return

        datos = respuesta.json()

        evento = {
            "tipo": "hit" if datos.get("cache_hit") else "miss",
            "consulta": mensaje.get("consulta", ""),
            "zona_id": mensaje.get("zona_id", ""),
            "latencia_ms": datos.get("latencia_ms", latencia_total),
            "cache_hit": datos.get("cache_hit", False),
            "clave": datos.get("clave", ""),
            "timestamp": time.time()
        }

        #registramos tambien metricas extra para la entrega 2 porsia
        evento_extra = {
            "tipo": "procesada_kafka",
            "consulta": mensaje.get("consulta", ""),
            "zona_id": mensaje.get("zona_id", ""),
            "latencia_ms": latencia_total,
            "cache_hit": datos.get("cache_hit", False),
            "clave": datos.get("clave", ""),
            "timestamp": time.time(),
            "retry_count": mensaje.get("retry_count", 0),
            "mensaje_id": mensaje.get("id", "")
        }

        await cliente.post(f"{METRICAS_URL}/registrar", json=evento, timeout=10)
        await cliente.post(f"{METRICAS_URL}/registrar", json=evento_extra, timeout=10)

        print(f"Consulta procesada {mensaje.get('id')} - {mensaje.get('consulta')} - retry {mensaje.get('retry_count', 0)}")

    except Exception as error:
        mandar_a_retry(producer, mensaje, str(error))


async def ejecutar_consumidor():
    consumer = crear_consumer()
    producer = crear_producer()

    print("Consumidor Kafka escuchando mensajes...")

    async with httpx.AsyncClient() as cliente:
        for mensaje_kafka in consumer:
            mensaje = mensaje_kafka.value
            await procesar_mensaje(cliente, producer, mensaje)


if __name__ == "__main__":
    import asyncio
    asyncio.run(ejecutar_consumidor())

if                                    

        a
    a
