# Extractor Service

Microservicio independiente para **extraer el contenido de archivos PDF en Markdown**, construido con FastAPI y [PyMuPDF](https://pypi.org/project/PyMuPDF/).

Forma parte de una arquitectura de microservicios más amplia: es un servicio aislado, sin dependencias de otros servicios, que expone una API RESTful asíncrona para recibir un PDF y devolver su texto junto con metadatos de la extracción (páginas, tamaño, tiempo de procesamiento).

## Características

- API asíncrona con **FastAPI**.
- Extracción con **PyMuPDF** (motor MuPDF, escrito en C), corrida en un thread aparte para no bloquear el event loop.
- El contenido sale en **Markdown**: las líneas con letra al menos 1.2 veces más grande que el cuerpo del documento son títulos (`# `) y cada bloque de texto es un párrafo. Es un Markdown mínimo a propósito: `pymupdf4llm` da un Markdown más completo pero, medido con los PDFs de carga, es entre 10 y 70 veces más lento que pypdf.
- Contratos de entrada/salida tipados con **Pydantic**. El Extractor solo limita el tamaño máximo (protección propia); validar el tipo de archivo o si está vacío es responsabilidad del **Validator**.
- Arquitectura en capas: endpoints HTTP, lógica de negocio y esquemas están desacoplados entre sí (principios SOLID/KISS/DRY/YAGNI).
- Suite de tests con **pytest**, desarrollada bajo un enfoque TDD, con PDFs generados en memoria de distintos tamaños (1, 10 y 100 páginas).
- Listo para contenedores: `Dockerfile` optimizado y `docker-compose.yml` propio del servicio.
- Cada réplica se registra en **Consul** al arrancar, y Traefik las descubre desde ahí (ver [Descubrimiento de servicios](#descubrimiento-de-servicios-consul)).

## Arquitectura del proyecto

```
pdf-extract-service/
├── app/
│   ├── main.py                       # Application factory (FastAPI) + /health + registro en Consul
│   ├── core/
│   │   ├── config.py                 # Configuración vía variables de entorno
│   │   ├── logging.py                # Logging del servicio según LOG_LEVEL
│   │   └── service_registry.py       # Registra y da de baja la réplica en Consul
│   ├── exceptions.py                 # Excepciones de dominio (agnósticas de HTTP)
│   ├── schemas/
│   │   ├── extraction.py             # DTOs Pydantic: entrada y salida
│   │   └── problem_details.py        # Cuerpo de error RFC 9457
│   ├── services/
│   │   ├── concurrency_limiter.py    # Backpressure: extracciones a la vez y cola de espera
│   │   ├── file_size.py              # Regla del tamaño máximo (413), compartida
│   │   ├── markdown_renderer.py      # Arma el Markdown (títulos y párrafos)
│   │   ├── pdf_extractor.py          # Lógica de negocio: extracción con PyMuPDF
│   │   └── throttled_extractor.py    # Decorador: extrae solo cuando el limitador da turno
│   └── api/
│       ├── dependencies.py           # Proveedores de dependencias compartidos
│       ├── error_handlers.py         # Traduce excepciones -> respuestas RFC 9457
│       ├── extract.py                # POST /extract (contrato del TP de carga)
│       └── v1/
│           ├── router.py
│           └── endpoints/
│               └── extraction.py     # POST /api/v1/extraer
├── tests/
│   ├── conftest.py                   # Fixtures: PDFs válidos generados en memoria
│   ├── test_pdf_extractor_service.py # Tests unitarios de la lógica de negocio
│   ├── test_schemas.py               # Tests del contrato de entrada
│   ├── test_extraction_endpoint.py   # Tests de integración de POST /api/v1/extraer
│   ├── test_extract_endpoint.py      # Tests de integración de POST /extract
│   ├── test_problem_details.py       # Tests del formato de errores RFC 9457
│   ├── test_concurrency_limiter.py   # Tests del limitador de concurrencia
│   ├── test_dependencies.py          # Tests de cómo los endpoints obtienen el servicio
│   ├── test_docker_compose.py        # Tests del compose: descubrimiento por Consul y circuit breaker
│   ├── test_service_registry.py      # Tests del registro en Consul (contra un Consul falso por HTTP)
│   ├── test_docker_image.py          # Tests de la imagen construida (solo con EXTRACTOR_IMAGE)
│   └── stress/                       # Pruebas de carga del TP (k6 y Vegeta)
│       ├── generate_pdfs.py          # Genera los 4 PDFs sintéticos
│       ├── pdfs/                     # Los 4 PDFs oficiales de la cátedra
│       ├── pdfs-sinteticos/          # liviano, mediano, largo y pesado
│       ├── k6-spike.js               # Spike: 0 → 100 VUs
│       ├── vegeta-constant.sh        # Carga fija: 50 req/s durante 30 s
│       └── results/                  # Salidas de cada medición
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .python-version                  # Versión de Python usada por uv
├── pyproject.toml                    # Dependencias y configuración (pytest, ruff)
└── uv.lock                           # Versiones exactas de las dependencias
```

**Principio de diseño:** el endpoint HTTP no conoce la lógica de extracción, y el servicio de extracción no conoce HTTP. Se comunican mediante excepciones de dominio (`app/exceptions.py`), que `app/api/error_handlers.py` traduce a respuestas de error [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457). Esto mantiene la lógica de negocio reutilizable fuera del contexto web.

## Requisitos previos

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) para manejar el entorno y las dependencias
- Docker y Docker Compose (opcional, para correr en contenedor)

## Instalación y entorno virtual

```bash
# Crea .venv e instala las dependencias de producción y desarrollo desde uv.lock
uv sync
```

No hace falta activar el entorno: `uv run <comando>` lo usa automáticamente.

> **Proyecto dentro de OneDrive:** si `uv sync` falla con *"os error 396"*, OneDrive no permite los hardlinks que uv usa por defecto. Definí `UV_LINK_MODE=copy` (en PowerShell: `$env:UV_LINK_MODE = "copy"`) y volvé a correrlo.

Para agregar una dependencia: `uv add <paquete>` (o `uv add --dev <paquete>` si es solo de desarrollo).

### Variables de entorno

Copiá el archivo de ejemplo y ajustá los valores si hace falta (los defaults ya son válidos para desarrollo local):

```bash
cp .env.example .env
```

| Variable                | Descripción                                   | Default                  |
|--------------------------|-----------------------------------------------|---------------------------|
| `APP_NAME`               | Nombre de la aplicación                       | `extractor-service`       |
| `APP_VERSION`            | Versión expuesta en `/docs`                   | `0.1.0`                   |
| `PORT`                   | Puerto HTTP de tu máquina donde Docker Compose publica Traefik (dentro de la red de Docker cada réplica escucha en `8000`) | `8080` |
| `HTTPS_PORT`             | Puerto HTTPS de tu máquina donde se publica Traefik, con certificado autofirmado | `443` |
| `MAX_FILE_SIZE_MB`       | Tamaño máximo de PDF aceptado (MB)            | `10`                      |
| `EXTRACTION_CONCURRENCY` | Extracciones simultáneas por proceso (mínimo 1). Ver [Backpressure](#backpressure) | `1` |
| `EXTRACTION_QUEUE_SIZE`  | Pedidos que pueden esperar turno por proceso antes de responder 503 | `20` |
| `RETRY_AFTER_SECONDS`    | Valor del header `Retry-After` del 503        | `1`                       |
| `LOG_LEVEL`              | Nivel de logging del servicio: `DEBUG`, `INFO`, `WARNING`, `ERROR` o `CRITICAL` (otro valor impide arrancar) | `INFO` |
| `CONSUL_URL`             | Dirección de Consul. Sin ella la réplica no se registra (desarrollo local, tests). El compose la define como `http://consul:8500` | — |
| `CONSUL_SERVICE_NAME`    | Nombre con el que la réplica se registra en Consul | `extractor` |
| `CONSUL_SERVICE_TAGS`    | Tags del registro, como lista JSON: es la configuración de Traefik (routers y circuit breaker). El compose los define | `[]` |
| `SERVICE_PORT`           | Puerto en el que escucha la réplica, el que Consul anuncia y chequea | `8000` |

## Levantar el servicio localmente

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Documentación interactiva (Swagger UI): http://localhost:8000/docs
- Documentación alternativa (ReDoc): http://localhost:8000/redoc
- Health check: http://localhost:8000/health

### Ejemplo de uso del endpoint

```bash
curl -X POST http://localhost:8000/api/v1/extraer \
  -F "file=@/ruta/a/documento.pdf;type=application/pdf"
```

Respuesta esperada:

```json
{
  "texto": "contenido extraído del PDF...",
  "metadatos": {
    "nombre_archivo": "documento.pdf",
    "tamanio_bytes": 24531,
    "cantidad_paginas": 3,
    "tiempo_procesamiento_ms": 12.4
  }
}
```

### Endpoint del TP de test de carga: `POST /extract`

Contrato pedido por el TP de test de carga y stress. Usa el mismo servicio de extracción que `/api/v1/extraer`, pero devuelve solo el contenido y la cantidad de páginas:

El PDF se puede enviar de dos formas:

```bash
# Como campo "file" de un multipart/form-data
curl -X POST http://localhost:8000/extract   -F "file=@/ruta/a/documento.pdf;type=application/pdf"

# Como body binario directo
curl -X POST http://localhost:8000/extract   -H "Content-Type: application/pdf"   --data-binary "@/ruta/a/documento.pdf"
```

```json
{
  "content": "contenido extraído del PDF...",
  "page_count": 3
}
```

Los errores son los mismos que los de `/api/v1/extraer` (ver abajo).

### Errores (RFC 9457)

Todos los errores se devuelven con `Content-Type: application/problem+json` siguiendo [RFC 9457 — Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457):

```json
{
  "type": "about:blank",
  "title": "Contenido no procesable",
  "status": 422,
  "detail": "El PDF no tiene texto extraíble.",
  "instance": "/api/v1/extraer"
}
```

| Status | `title`                      | Cuándo |
|--------|------------------------------|--------|
| `413`  | Contenido demasiado grande   | El archivo supera `MAX_FILE_SIZE_MB` |
| `422`  | Contenido no procesable      | El archivo no es un PDF legible (incluido un archivo vacío), el PDF no tiene texto extraíble (por ejemplo, páginas en blanco o escaneadas), o falta el campo `file` (en este caso el cuerpo incluye además `errors` con el detalle de cada campo) |
| `404`  | No encontrado                | La ruta no existe |
| `405`  | Método no permitido          | El método HTTP no está permitido en esa ruta |
| `503`  | Servicio no disponible       | Las extracciones en curso y la cola de espera están llenas (backpressure). Incluye el header `Retry-After` |
| `500`  | Error interno del servidor   | Error inesperado. El `detail` es genérico; la causa real solo queda en el log del servicio |

Los campos de la respuesta, los títulos y los mensajes (`detail`) están en español. La lista `errors` que acompaña al 422 por campo faltante conserva los mensajes originales de FastAPI (en inglés).

## Correr los tests (pytest)

```bash
uv run pytest
```

Modo verboso:

```bash
uv run pytest -v
```

Con reporte de cobertura:

```bash
uv run pytest --cov=app --cov-report=term-missing
```

Correr solo un archivo o clase de tests puntual:

```bash
uv run pytest tests/test_pdf_extractor_service.py -v
uv run pytest tests/test_extraction_endpoint.py::TestExtractEndpointSuccess -v
```

Linter:

```bash
uv run ruff check .
```

Tests de la imagen Docker: levantan contenedores de una imagen ya construida, así que se saltean salvo que `EXTRACTOR_IMAGE` indique cuál probar. Verifican que no lleve `uv` ni `pip`, que tenga los paquetes de Debian con los arreglos de seguridad, que la app cargue y que corra sin root (ver [Seguridad de la imagen](#seguridad-de-la-imagen-grype)):

```bash
docker build -t extractor-service:latest .
EXTRACTOR_IMAGE=extractor-service:latest uv run pytest tests/test_docker_image.py -v
```

Los fixtures en `tests/conftest.py` generan PDFs válidos en memoria (no hay binarios versionados), lo que permite cubrir distintos tamaños de archivo:

- `small_pdf_bytes` → 1 página
- `medium_pdf_bytes` → 10 páginas
- `large_pdf_bytes` → 100 páginas
- `blank_pdf_bytes` → PDF válido sin texto (página en blanco)
- `corrupted_pdf_bytes` / `not_a_pdf_bytes` / `empty_file_bytes` → casos inválidos

## Uso con Docker Compose

El compose levanta el Extractor **escalado horizontalmente** detrás de un reverse proxy:

```
cliente ──► Traefik (:8080 HTTP · :443 HTTPS) ──► extractor réplica 1 … réplica 5 (:8000 interno)
               │                                         │
               └──── ¿qué réplicas hay? ──► Consul ◄──── se registran al arrancar
```

- **Traefik** es el único servicio con puerto publicado. Le pregunta a **Consul** qué réplicas hay y reparte los pedidos entre las que tienen el health check sano (ver [Descubrimiento de servicios](#descubrimiento-de-servicios-consul)).
- **consul** es el registro de servicios. No publica puertos: solo lo usan Traefik y las réplicas, dentro de la red de Docker.
- **extractor** corre `EXTRACTOR_REPLICAS` réplicas (5 por defecto, el máximo que permite el TP), cada una limitada a **1 CPU y 512 MB** de RAM. Traefik también tiene 1 CPU y 512 MB: bajo la prueba de Vegeta llegó a usar unos 210 MB.
- Traefik protege a las réplicas con un **circuit breaker** (ver [Circuit breaker](#circuit-breaker)).

1. (Opcional) Si querés cambiar algún valor por defecto, creá un `.env` a partir de `.env.example` y editalo. Sin `.env` se usan los valores por defecto:

   ```bash
   cp .env.example .env
   ```

2. Levantar todo:

   ```bash
   docker compose up --build
   ```

3. El servicio queda disponible en:
   - `http://localhost:8080` (o el puerto que definas en `PORT`). Es donde apunta el archivo de objetivos de Vegeta de la cátedra.
   - `https://localhost` o `https://extract.universidad.localhost` (puerto `HTTPS_PORT`, 443 por defecto). Es donde apunta el script de k6 de la cátedra. El certificado lo genera Traefik y es autofirmado: con k6 hay que agregar `--insecure-skip-tls-verify` y con curl `-k`. La alternativa es usar `http://localhost:8080`.
   - Traefik responde a cualquier nombre de host, así que no hace falta configurar ningún dominio.

4. Para correrlo en segundo plano:

   ```bash
   docker compose up -d --build
   ```

5. Para ver las réplicas y su estado:

   ```bash
   docker compose ps
   ```

6. Para detenerlo:

   ```bash
   docker compose down
   ```

### Build manual de la imagen (sin compose)

```bash
docker build -t extractor-service:latest .
docker run --rm -p 8000:8000 extractor-service:latest
# con variables propias: docker run --rm -p 8000:8000 --env-file .env extractor-service:latest
```

El contenedor corre como usuario no-root, expone el puerto `8000` y define un `HEALTHCHECK` contra `/health`.

### Seguridad de la imagen (grype)

[grype](https://github.com/anchore/grype) busca vulnerabilidades conocidas (CVE) en todo lo que trae la imagen: los paquetes de Debian de la imagen base, el intérprete de Python, las dependencias del `.venv` y cualquier binario suelto. No hace falta instalarlo; corre en un contenedor:

```bash
docker build -t extractor-service:latest .
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v grype-db:/root/.cache/grype \
  anchore/grype:latest extractor-service:latest
```

La primera vez descarga su base de datos de vulnerabilidades (el volumen `grype-db` la guarda para las siguientes). En Git Bash hay que anteponer `MSYS_NO_PATHCONV=1`.

Para reducir lo que reporta, el `Dockerfile` construye en dos etapas: la imagen final no lleva nada que el servicio no use al correr.

| Cambio | Qué quitó |
|--------|-----------|
| `uv` solo en la etapa de construcción | Las librerías de Rust que trae el binario de `uv` (`rustls`) |
| `pip` desinstalado (las dependencias se instalan con `uv`) | `pip` 25.0.1, que viene en la imagen base |
| `apt-get upgrade` | `zlib1g` con dos CVE High ya corregidos en Debian, que la imagen oficial todavía no incluía |

Resultado (grype 0.121.3, noviembre de 2026):

| | Antes | Después |
|--|-------|---------|
| Vulnerabilidades | 202 (61 High) | 189 (59 High) |
| Con arreglo disponible | 21 | 8 |
| Tamaño de la imagen | 700 MB | 333 MB |

- **Las dependencias propias del servicio** (`fastapi`, `pymupdf`, `requests`, `uvicorn`, etc.) no tienen vulnerabilidades reportadas.
- **Las 8 con arreglo que quedan son del intérprete Python 3.12.** Se corrigen en Python 3.13 o 3.14; cambiar de versión obliga a repetir las pruebas de carga, así que es una decisión aparte.
- **Las otras 181 son paquetes de Debian sin arreglo publicado** (`libc`, `util-linux`, `ncurses`…), las mismas en cualquier imagen basada en `python:3.12-slim`. Se resuelven solas al reconstruir cuando Debian publique los arreglos (el `apt-get upgrade` los toma).

## Backpressure

Cada proceso extrae como máximo `EXTRACTION_CONCURRENCY` PDFs a la vez (1 por defecto). Los pedidos que llegan mientras tanto **esperan su turno en orden**, hasta `EXTRACTION_QUEUE_SIZE` (20). Si la cola también está llena, el servicio responde **`503` al instante** con `Retry-After`, en lugar de aceptar un pedido que va a esperar más de lo que el cliente tolera.

```
pedido ──► ¿hay lugar? ──no──► 503 + Retry-After (inmediato)
               │ sí
               ▼
         cola en orden ──► 1 extracción a la vez ──► 200
```

**Por qué:** en las pruebas de carga, cuando muchos pedidos extraían al mismo tiempo en una réplica, competían por el GIL y por su única CPU, y el throughput caía a la mitad (6.22 req/s con 1 pedido por réplica contra 3.06 req/s con ~20). Además, los pedidos que esperaban más que el timeout del cliente se seguían procesando para nadie.

- `ConcurrencyLimiter` (`app/services/concurrency_limiter.py`) cuenta los pedidos en curso y en espera, y los hace esperar con un semáforo.
- `ThrottledExtractor` (`app/services/throttled_extractor.py`) envuelve al servicio de extracción con la misma interfaz (`PDFExtractor`): el servicio no sabe nada de concurrencia.
- Hay un solo limitador por proceso, compartido por `/extract` y `/api/v1/extraer`.

## Circuit breaker

Si las réplicas dejan de responder, Traefik **deja de mandarles pedidos por un tiempo** y responde `503` al instante, en lugar de dejar a cada cliente esperando. Así una falla no se propaga a quien llama (fallo en cascada) y las réplicas se recuperan sin recibir más carga.

Lo maneja **Traefik**, no el código Python. Es una cuestión de infraestructura (SRP): el Extractor no sabe que existe. Se configura con un middleware en los tags de Consul (`CONSUL_SERVICE_TAGS` en `docker-compose.yml`) y se aplica a los dos routers, HTTP y HTTPS.

```
CERRADO ──más del 50% de errores de red──► ABIERTO ──10 s──► SEMIABIERTO
   ▲         (pedidos normales)            (503 inmediato)   (deja pasar de a poco)
   └──────────────────── responden bien durante 10 s ───────────────┘
```

| Parámetro del patrón | Valor | Dónde | Por qué |
|----------------------|-------|-------|---------|
| Tiempo de expiración | `60s` | `--serversTransport.forwardingTimeouts.responseHeaderTimeout` (Traefik) | Sin timeout, Traefik espera para siempre a una réplica colgada y la falla nunca se cuenta. 60 s es el timeout de k6; en el spike los pedidos legítimos tardaron hasta 44 s por la cola del backpressure, así que ninguno se corta. |
| Umbral | `NetworkErrorRatio() > 0.50` | `circuitbreaker.expression` | Cuenta solo errores de red (`502`/`504`: réplica caída o que superó el timeout). El `503` del [backpressure](#backpressure) no cuenta: si contara, el circuito se abriría justo bajo carga, cuando el servicio está funcionando bien. |
| Ventana (abierto) | `10s` | `circuitbreaker.fallbackDuration` | Tiempo en que responde `503` sin llamar a las réplicas. |
| Semiabierto | `10s` | `circuitbreaker.recoveryDuration` | Tiempo en que vuelve a dejar pasar el tráfico de a poco antes de cerrarse. |

**Cómo comprobarlo** con el compose levantado, pausando todas las réplicas:

```bash
docker compose pause extractor
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" http://localhost:8080/health   # repetir varias veces
docker compose unpause extractor
```

Los primeros pedidos responden `504` al vencer el timeout; con más de la mitad fallando, el circuito se abre y los siguientes responden `503` en milisegundos. Después de reanudar las réplicas sigue respondiendo `503` durante la ventana, y vuelve a `200` cuando termina la recuperación. Con el timeout de 60 s cada `504` tarda un minuto; con un timeout de 3 s se observó: `504` (3 s), `504` (3 s), `503` (0.005 s) × 4 y, unos 20 s después de reanudar, `200`.

- Si las réplicas siguen sin responder, a los ~15 s Consul marca sus health checks como críticos y Traefik saca el servicio: ahí responde `404` en lugar de `503` (ver [limitaciones](#limitaciones)).
- Cada vez que cambia lo que hay en Consul, Traefik recarga su configuración y el circuit breaker empieza de cero. Por eso conviene esperar unos 20 s después de levantar el compose antes de probarlo: en los primeros segundos Traefik recibe varias actualizaciones seguidas.

`tests/test_docker_compose.py` fija esta configuración: lee los tags del compose igual que Traefik.

## Descubrimiento de servicios (Consul)

Las réplicas no tienen una dirección fija: cada contenedor recibe una IP al arrancar, y se pueden levantar o apagar réplicas en cualquier momento. **Consul** es el registro donde cada réplica anota dónde está, y Traefik lo consulta para saber a quién mandarle los pedidos (patrón *Service Discovery*).

```
1. Al arrancar, cada réplica se registra:   PUT /v1/agent/service/register
   {ID: "extractor-<hostname>", Address: <su IP>, Port: 8000, Tags: [...], Check: GET /health cada 10 s}
2. Consul le pega a /health de cada réplica y sabe cuáles están sanas.
3. Traefik escucha a Consul (watch) y arma sus routers con los tags de las réplicas sanas.
4. Al apagarse (SIGTERM), la réplica se da de baja:   PUT /v1/agent/service/deregister/<ID>
```

- **Dónde está el código:** `app/core/service_registry.py` registra y da de baja la réplica con `requests`, y el `lifespan` de `app/main.py` lo llama al arrancar y al apagarse. Es infraestructura: la lógica de extracción no sabe que Consul existe.
- **Los tags vienen del entorno** (`CONSUL_SERVICE_TAGS`): el código no conoce Traefik, y la configuración de ruteo sigue en el compose.
- **Sin `CONSUL_URL` la réplica no se registra**, así funcionan igual `uv run uvicorn …`, los tests y cualquier compose sin Consul (por ejemplo el de integración del Orchestrator).
- **Si Consul no responde al arrancar, la réplica no levanta** (fail fast): una réplica que Traefik no puede descubrir nunca recibiría tráfico. Docker la reinicia (`restart: unless-stopped`).
- **Si falla la baja al apagarse, solo se loguea un warning:** Consul la borra igual cuando su health check lleva un minuto en estado crítico (`DeregisterCriticalServiceAfter`).

**Por qué Consul y no las labels de Docker:** antes Traefik descubría las réplicas leyendo las labels a través de la API de Docker, para lo cual montaba `/var/run/docker.sock`. Ese socket da control sobre Docker (crear contenedores, montar el disco del host), así que un Traefik comprometido comprometía la máquina. Con Consul, Traefik ya no lo necesita. Además el descubrimiento deja de depender de Docker.

**Por qué `watch=true`:** por defecto Traefik le pregunta a Consul cada 15 s. Al apagar una réplica, durante ese intervalo seguía mandándole pedidos: fallaron 3 de 20. Con `watch` Traefik se entera al instante: 40 de 40 respondieron `200` mientras se apagaban réplicas.

**Cómo verlo** con el compose levantado:

```bash
# Servicios registrados
docker compose exec consul consul catalog services

# Estado del health check de cada réplica (una entrada por réplica, "Status": "passing")
docker compose exec consul wget -qO- http://127.0.0.1:8500/v1/health/checks/extractor

# Apagar una réplica: se da de baja y Traefik deja de mandarle pedidos
docker stop pdf-extract-service-extractor-1
docker start pdf-extract-service-extractor-1
```

### Limitaciones

- **Con todas las réplicas caídas, Traefik responde `404`, no `503`.** Cuando Consul marca todos los health checks como críticos, Traefik borra el router. El provider de Consul de Traefik v3.6 no tiene la opción `allowEmptyServices` del provider de Docker, que lo resolvería (se probó: Traefik no arranca con ese flag).
- **Consul corre en modo `-dev`:** un solo nodo, con los datos en memoria. Alcanza para el TP porque las réplicas se vuelven a registrar solas al arrancar; en producción serían varios servidores para tolerar la caída de uno.

## Pruebas de carga (TP de test de carga y stress)

Los scripts en `tests/stress/` reproducen las dos pruebas con las que la cátedra compara las entregas. Pegan contra `POST /extract` a través de Traefik, con las 5 réplicas levantadas.

| Prueba | Script | Perfil | Envío del PDF |
|--------|--------|--------|---------------|
| Spike (modelo cerrado) | `k6-spike.js` | 0 → 100 VUs en 10 s, 20 s a 100 VUs, 100 → 0 en 10 s | multipart (`file`) |
| Carga fija (modelo abierto) | `vegeta-constant.sh` | 50 req/s durante 30 s (1.500 pedidos), timeout 30 s | body binario |

Las dos pruebas rotan en orden los PDFs del set elegido, así cada corrida manda la misma mezcla.

### PDFs de prueba

Hay dos sets. La variable `PDF_SET` elige cuál usan los scripts.

**`profesor` (por defecto): `tests/stress/pdfs/`.** Los 4 documentos oficiales que entregó la cátedra; es la carpeta que nombra el TP.

| PDF | Páginas | Tamaño | Extracción (1, en reposo) |
|-----|---------|--------|---------------------------|
| `2020-Scrum-Guide-Spanish-Latin-South-American.pdf` | 16 | 0.30 MB | 41 ms |
| `Essential-Kanban-Condensed-Spanish.pdf` | 90 | 8.49 MB | 147 ms |
| `Filosofia Lean.pdf` | 42 | 0.64 MB | 93 ms |
| `scrum_manager_historias_usuario.pdf` | 62 | 3.65 MB | 80 ms |

**`sinteticos`: `tests/stress/pdfs-sinteticos/`.** Generados por `tests/stress/generate_pdfs.py` (semilla fija, mismos archivos byte a byte en cada corrida). Se usaron para la línea de base y las primeras optimizaciones, antes de tener los documentos oficiales. Son más exigentes para la CPU por `largo.pdf`.

| PDF | Páginas | Tamaño | Qué estresa |
|-----|---------|--------|-------------|
| `liviano.pdf` | 2 | 0.01 MB | El costo fijo de cada pedido |
| `mediano.pdf` | 30 | 0.13 MB | Un documento típico |
| `largo.pdf` | 300 | 1.36 MB | La CPU durante la extracción |
| `pesado.pdf` | 12, con una imagen grande por página | 9.02 MB | La subida y la memoria |

```bash
uv run python tests/stress/generate_pdfs.py
```

### Cómo correrlas

No hace falta instalar k6 ni Vegeta: corren en contenedores. Con el servicio levantado (`docker compose up -d --build`), desde la raíz del repo:

```bash
# Spike con k6 (imagen oficial grafana/k6)
docker run --rm -v "$PWD/tests/stress:/scripts" \
  -e BASE_URL=http://host.docker.internal:8080 \
  grafana/k6 run /scripts/k6-spike.js

# Carga fija con Vegeta (imagen de la comunidad peterevans/vegeta)
docker run --rm -v "$PWD/tests/stress:/scripts" \
  -e BASE_URL=http://host.docker.internal:8080 \
  --entrypoint sh peterevans/vegeta /scripts/vegeta-constant.sh
```

En Git Bash (Windows) hay que anteponer `MSYS_NO_PATHCONV=1` y usar `$(pwd -W)` en lugar de `$PWD`, para que no se reescriban las rutas del contenedor.

- `BASE_URL` apunta al servicio. `host.docker.internal` es la máquina anfitriona vista desde el contenedor.
- `PDF_SET=sinteticos` (agregado con `-e`) corre las pruebas con los PDFs generados.
- El script de Vegeta acepta además `RATE`, `DURATION` y `TIMEOUT` (por defecto, `50`, `30s` y `30s`).
- El script de k6 comparte una sola copia de los PDFs entre los 100 VUs (`k6/experimental/fs`). Con el `open()` clásico cada VU tendría su propia copia: unos 1.4 GB de RAM.
- Correr un proyecto por vez (`docker compose down` entre uno y otro): otro proyecto con su propio Traefik en el mismo Docker compite por el puerto 8080 y por los recursos de la máquina, y altera las mediciones.

Las salidas de cada medición se guardan en `tests/stress/results/`, nombradas por prueba, set de PDFs o motor de extracción, y cantidad de réplicas.

### Condiciones de medición

Los resultados de `tests/stress/results/` se midieron en una notebook con un i5-1135G7 (4 núcleos físicos, 8 hilos) y 7.6 GB de RAM, con Docker Desktop limitado a 3.9 GB y el generador de carga en la misma máquina. Con los PDFs oficiales, k6 llega a usar más de 5 hilos solo para generar la carga, y dos corridas iguales variaron hasta un 40% según la memoria libre del equipo. En una máquina con más núcleos y memoria los números deberían ser mejores.

## Stack técnico

| Componente         | Herramienta            |
|---------------------|-------------------------|
| Framework web        | FastAPI                |
| Servidor ASGI         | Uvicorn                |
| Extracción de PDF     | PyMuPDF (AGPL)         |
| Validación de datos   | Pydantic / pydantic-settings |
| Testing                | pytest, pytest-asyncio, httpx2 |
| Dependencias           | uv                     |
| Contenedores            | Docker / Docker Compose |
| Reverse proxy           | Traefik v3.6           |
| Descubrimiento de servicios | Consul 1.21 (cliente HTTP: requests) |
| Pruebas de carga        | Grafana k6, Vegeta     |
