# Tarea 1 - Sistemas Distribuidos 2026-1
## Plataforma de cache distribuida para analisis de edificaciones

### Descripción
En esta tarea implementamos un sistema distribuido que permite responder consultas sobre edificaciones en la region metropolitana. La idea principal fue usar un sistema de cache para mejorar el tiempo de respuesta cuando se repiten consultas.
El enfoque fue simular trafico real (no solo consultas al azar) y ver como cambia el rendimiento dependiendo de la distribución de las consultas y configuración de Redis.

### Arquitectura
Separamos el sistema en varios servicios para que cada uno tenga una responsabilidad clara:

- **generador_trafico**: genera consultas automáticas siguiendo distribución Zipf o uniforme
- **servicio_cache**: recibe las consultas y decide si responder desde cache o consultar
- **generador_respuestas**: calcula los resultados usando los datos de memoria 
- **almacenamiento_metricas**: guarda métricas para después analizarlas

## Flujo del sistema

El sistema sigue un flujo secuencial entre sus servicios principales para simular un escenario real de consultas repetitivas sobre edificaciones en la Región Metropolitana.

1. El **generador de tráfico** crea consultas automáticas sobre las zonas predefinidas (Z1–Z5), utilizando distribución **Zipf** o **uniforme**, dependiendo de la configuración definida en `.env`.

2. Cada consulta es enviada al **servicio de caché**, donde se genera una `cache key` única basada en el tipo de consulta, la zona y sus parámetros asociados.

3. Si la respuesta ya existe en Redis (**cache hit**), esta se retorna inmediatamente al cliente, reduciendo la latencia de respuesta y registrando el evento en el sistema de métricas.

4. Si la respuesta no existe (**cache miss**), la consulta se deriva al **generador de respuestas**, que procesa la operación utilizando los datos precargados en memoria desde el dataset Google Open Buildings.

5. El resultado obtenido se almacena en Redis utilizando el TTL configurado, permitiendo futuras reutilizaciones de la respuesta.

6. Paralelamente, el sistema registra métricas relevantes como hits, misses, latencia, throughput y evicciones para su posterior análisis experimental.

Este flujo permite evaluar el comportamiento de la caché bajo distintas condiciones de carga y configuraciones de Redis.

---

## Métricas registradas

Para analizar el rendimiento del sistema se registran las siguientes métricas:

| Métrica | Descripción |
|---|---|
| Hit Rate | Proporción de consultas respondidas directamente desde caché |
| Miss Rate | Consultas que requieren procesamiento completo |
| Throughput | Número de consultas exitosas por segundo |
| Latencia p50 / p95 | Tiempo de respuesta promedio y en escenarios de mayor carga |
| Eviction Rate | Número de claves eliminadas por minuto |
| Cache Efficiency | Relación entre beneficio de cache hits y costo de cache misses |

Estas métricas permiten comparar el impacto de la distribución de tráfico, el tamaño de caché, las políticas de reemplazo y el valor del TTL.

---

## Justificación de decisiones de diseño

### Uso de Redis

Se utilizó Redis como sistema de caché debido a su baja latencia, soporte nativo para TTL, políticas de evicción configurables y facilidad de integración mediante Docker. Esto permite simular de forma realista un sistema distribuido orientado a alto rendimiento.

### Distribución Zipf

La distribución Zipf fue utilizada porque representa mejor patrones reales de acceso, donde ciertas zonas reciben muchas más consultas que otras. Esto permite modelar el concepto de **locality of reference**, aumentando naturalmente la probabilidad de cache hits.

La distribución uniforme se utiliza como contraste experimental para evaluar el comportamiento del sistema en un escenario sin sesgo de popularidad.

### Tamaños de caché

Se evaluaron tres tamaños de caché:

- 50 MB
- 200 MB
- 500 MB

Esto permite analizar cómo cambia el hit rate y la eficiencia del sistema a medida que aumenta la capacidad de almacenamiento disponible.

### Políticas de reemplazo

Se comparan distintas políticas de evicción como:

- LRU (Least Recently Used)
- LFU (Least Frequently Used)
- Random

Esto permite observar diferencias entre estrategias basadas en temporalidad de acceso versus frecuencia de uso.

---

## Experimentos realizados

El análisis experimental del sistema considera los siguientes escenarios:

### Comparación de distribución de tráfico

Se compara el comportamiento de la caché utilizando:

- Distribución uniforme
- Distribución Zipf

El objetivo es medir cómo afecta cada patrón de acceso sobre el hit rate, la latencia y el throughput.

### Evaluación de tamaño de caché

Se analiza el impacto de distintos tamaños de memoria configurando Redis con:

- 50 MB
- 200 MB
- 500 MB

Se observa especialmente el efecto sobre la tasa de aciertos y la tasa de evicción.

### Evaluación de políticas de reemplazo

Se comparan al menos dos políticas de remoción para estudiar su efecto sobre el rendimiento general del sistema:

- LRU
- LFU
- Random

### Evaluación de TTL

Se analiza cómo distintos valores de TTL afectan la permanencia de las respuestas en caché y su impacto en consultas repetidas, especialmente en escenarios de alta concurrencia.

Estos experimentos permiten justificar técnicamente las decisiones de diseño adoptadas y respaldar el análisis presentado en el informe técnico.

### Requisitos
- Docker Desktop instalado y corriendo
- Tener puertos disponibles 8001, 8002, 8003 y 6379

### Despliegue

1. Clonar el repositorio:
```bash
git clone https://github.com/Rostertag1/tarea1-sistemas-distribuidos.git
cd tarea1-sistemas-distribuidos/entrega_1
```

2. Configurar el archivo `.env`:
REDIS_MAXMEMORY=200mb
REDIS_POLICY=allkeys-lru
TTL_SEGUNDOS=60
DISTRIBUCION=zipf
TOTAL_CONSULTAS=1000
INTERVALO_SEGUNDOS=0.1

3. Levanta el sistema:
```bash
docker compose up --build
```

### Parámetros configurables (.env)

| Parámetro | Descripción | Valores posibles |
|---|---|---|
| REDIS_MAXMEMORY | Tamaño máximo de la caché | 50mb, 200mb, 500mb |
| REDIS_POLICY | Política de evicción | allkeys-lru, allkeys-lfu, allkeys-random |
| TTL_SEGUNDOS | Tiempo de vida de las claves | cualquier entero positivo |
| DISTRIBUCION | Distribución del tráfico | zipf, uniforme |
| TOTAL_CONSULTAS | Número de consultas a generar | cualquier entero positivo |

### Endpoints disponibles

| Servicio | Endpoint | Descripción |
|---|---|---|
| generador_respuestas | GET /q1/{zona_id} | Conteo de edificios |
| generador_respuestas | GET /q2/{zona_id} | Área promedio y total |
| generador_respuestas | GET /q3/{zona_id} | Densidad por km² |
| generador_respuestas | GET /q4/{zona_a}/{zona_b} | Comparación entre zonas |
| generador_respuestas | GET /q5/{zona_id} | Distribución de confianza |
| servicio_cache | GET /consulta/q1/{zona_id} | Q1 con caché |
| almacenamiento_metricas | GET /metricas | Ver métricas del sistema |
| almacenamiento_metricas | DELETE /metricas/limpiar | Limpiar métricas |

### Zonas disponibles
| ID | Nombre | 
|---|---|
| Z1 | Providencia |
| Z2 | Las Condes |
| Z3 | Maipú |
| Z4 | Santiago Centro |
| Z5 | Pudahuel |

### Integrantes
- Rafael Ostertag
- Valentina Aguirre