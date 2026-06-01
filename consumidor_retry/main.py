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


