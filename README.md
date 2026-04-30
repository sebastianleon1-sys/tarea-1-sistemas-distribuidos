# Tarea 1 - Sistemas Distribuidos

Plataforma de análisis de consultas geoespaciales con caché distribuida usando Redis.

## Descripción

Este proyecto implementa una simulación de caché aplicada a consultas geoespaciales sobre el dataset Google Open Buildings. El sistema trabaja con cinco zonas predefinidas de la Región Metropolitana de Santiago de Chile y permite evaluar el comportamiento de distintas políticas de caché bajo diferentes tamaños de memoria y distribuciones de tráfico.

La arquitectura del sistema está compuesta por:

- Generador de tráfico.
- Caché Redis.
- Generador de respuestas.
- Sistema de métricas.

El sistema ejecuta consultas sintéticas Q1-Q5 sobre datos precargados en memoria y registra métricas como hit rate, miss rate, throughput, latencia p50, latencia p95, eviction rate y cache efficiency.

## Tecnologías utilizadas

- Python 3.11
- Redis 7
- Docker
- Docker Compose
- Pandas
- Matplotlib

## Estructura del proyecto

```text
.
├── app/
│   ├── cache.py
│   ├── data.py
│   ├── main.py
│   ├── metrics.py
│   ├── queries.py
│   ├── traffic_generator.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── data/
│       └── 967_buildings.csv.gz
├── docker-compose.yml
├── run_experiments.py
├── README.md
└── .gitignore
```

## Dataset

El dataset no se incluye en el repositorio debido a su tamaño.

Antes de ejecutar el sistema, se debe copiar el archivo:

```text
967_buildings.csv.gz

download:

https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_4_gzip/967_buildings.csv.gz
```

en la siguiente ruta:

```text
app/data/967_buildings.csv.gz
```

El archivo debe contener las siguientes columnas:

- latitude
- longitude
- area_in_meters
- confidence

## Zonas utilizadas

El sistema trabaja con cinco zonas predefinidas:

| ID | Zona |
|---|---|
| Z1 | Providencia |
| Z2 | Las Condes |
| Z3 | Maipú |
| Z4 | Santiago Centro |
| Z5 | Pudahuel |

## Consultas implementadas

| Consulta | Descripción |
|---|---|
| Q1 | Conteo de edificios en una zona |
| Q2 | Área promedio y área total de edificios |
| Q3 | Densidad de edificios por km² |
| Q4 | Comparación de densidad entre dos zonas |
| Q5 | Distribución de confianza en una zona |

## Ejecución básica

Desde la raíz del proyecto, ejecutar:

```bash
docker compose up --build
```

Este comando levanta Redis y ejecuta la aplicación con la configuración definida en `docker-compose.yml`.

## Ejecutar una simulación específica

Primero se debe levantar Redis:

```bash
docker compose up -d redis
```

Para ejecutar la distribución Zipf:

```bash
docker compose run --rm app python main.py --distribution zipf --queries 10000 --ttl 300 --seed 42
```

Para ejecutar la distribución uniforme:

```bash
docker compose run --rm app python main.py --distribution uniform --queries 10000 --ttl 300 --seed 42
```

Para ejecutar ambas distribuciones:

```bash
docker compose run --rm app python main.py --distribution both --queries 10000 --ttl 300 --seed 42
```

## Ejecutar todos los experimentos

Para ejecutar los 18 experimentos definidos en la tarea:

```bash
python run_experiments.py
```

Este script evalúa:

- 3 políticas de caché:
  - LRU
  - LFU
  - FIFO aproximado mediante `volatile-ttl`
- 3 tamaños de caché:
  - 50 MB
  - 200 MB
  - 500 MB
- 2 distribuciones de tráfico:
  - Zipf
  - Uniforme

Cada experimento ejecuta:

- 10.000 consultas.
- TTL fijo de 300 segundos.
- Seed 42.

Los resultados se guardan en:

```text
experiment_results/
```

## Regenerar gráficos

Si ya existen resultados en `experiment_results/all_results.json`, se pueden regenerar solo los gráficos con:

```bash
python run_experiments.py --plots-only
```

## Gráficos generados

Los gráficos principales generados por el sistema son:

```text
01_hit_rate_politica_tamano_distribucion.png
02_miss_rate_politica_tamano_distribucion.png
03_zipf_vs_uniform_lru_todos_tamanos.png
04_latencias_p50_p95_50mb.png
05_eviction_rate_lru_por_tamano.png
06_hit_rate_por_query_q1_q5.png
```

## Políticas de caché evaluadas

| Nombre en informe | Política Redis |
|---|---|
| LRU | allkeys-lru |
| LFU | allkeys-lfu |
| FIFO aproximado | volatile-ttl |

Redis no implementa FIFO puro como política estándar de evicción. Por esta razón, el proyecto utiliza `volatile-ttl` como aproximación, ya que todas las claves se almacenan con TTL fijo y las más antiguas tienden a tener menor tiempo restante.

## Variables importantes

En `docker-compose.yml` se define la variable:

```text
CACHE_PAYLOAD_BYTES=75000
```

Esta variable permite simular respuestas geoespaciales más pesadas dentro de Redis. El resultado lógico de la consulta no cambia, pero sí aumenta el tamaño físico almacenado en caché. Esto permite observar mejor el efecto de los límites de memoria y de las políticas de evicción.

## Métricas registradas

El sistema registra:

- Total de consultas.
- Hits.
- Misses.
- Hit rate.
- Miss rate.
- Throughput.
- Latencia p50.
- Latencia p95.
- Eviction rate.
- Cache efficiency.
- Hit rate por tipo de consulta.

## Video de demostración

https://youtu.be/hNh-GjBrcW4

## Autor

Sebastián León  
Universidad Diego Portales  
Sistemas Distribuidos 2026
