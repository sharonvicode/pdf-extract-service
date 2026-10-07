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

## Arquitectura del proyecto

```
pdf-extract-service/
├── app/
│   ├── main.py                       # Application factory (FastAPI) + /health
│   ├── core/
│   │   ├── config.py                 # Configuración vía variables de entorno
│   │   └── logging.py                # Logging del servicio según LOG_LEVEL
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
│   └── stress/                       # Pruebas de carga del TP (k6 y Vegeta)
│       ├── generate_pdfs.py          # Genera los 4 PDFs de prueba
│       ├── pdfs/                     # liviano, mediano, largo y pesado
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
| `PORT`                   | Puerto de tu máquina donde Docker Compose publica el servicio (dentro del contenedor siempre es `8000`) | `8000` |
| `MAX_FILE_SIZE_MB`       | Tamaño máximo de PDF aceptado (MB)            | `10`                      |
| `EXTRACTION_CONCURRENCY` | Extracciones simultáneas por proceso (mínimo 1). Ver [Backpressure](#backpressure) | `1` |
| `EXTRACTION_QUEUE_SIZE`  | Pedidos que pueden esperar turno por proceso antes de responder 503 | `20` |
| `RETRY_AFTER_SECONDS`    | Valor del header `Retry-After` del 503        | `1`                       |
| `LOG_LEVEL`              | Nivel de logging del servicio: `DEBUG`, `INFO`, `WARNING`, `ERROR` o `CRITICAL` (otro valor impide arrancar) | `INFO` |

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

Los fixtures en `tests/conftest.py` generan PDFs válidos en memoria (no hay binarios versionados), lo que permite cubrir distintos tamaños de archivo:

- `small_pdf_bytes` → 1 página
- `medium_pdf_bytes` → 10 páginas
- `large_pdf_bytes` → 100 páginas
- `blank_pdf_bytes` → PDF válido sin texto (página en blanco)
- `corrupted_pdf_bytes` / `not_a_pdf_bytes` / `empty_file_bytes` → casos inválidos

## Uso con Docker Compose

El compose levanta el Extractor **escalado horizontalmente** detrás de un reverse proxy:

```
cliente ──► Traefik (:8000) ──► extractor réplica 1 … réplica 5 (:8000 interno)
```

- **Traefik** es el único servicio con puerto publicado. Descubre las réplicas a través de la API de Docker (por eso monta `/var/run/docker.sock` en solo lectura) y reparte los pedidos entre ellas. Solo envía tráfico a las réplicas cuyo healthcheck está sano.
- **extractor** corre `EXTRACTOR_REPLICAS` réplicas (5 por defecto, el máximo que permite el TP), cada una limitada a **1 CPU y 512 MB** de RAM. Traefik también tiene 1 CPU y 512 MB: bajo la prueba de Vegeta llegó a usar unos 210 MB.

1. (Opcional) Si querés cambiar algún valor por defecto, creá un `.env` a partir de `.env.example` y editalo. Sin `.env` se usan los valores por defecto:

   ```bash
   cp .env.example .env
   ```

2. Levantar todo:

   ```bash
   docker compose up --build
   ```

3. El servicio queda disponible en `http://localhost:8000` (o el puerto que definas en `PORT`).

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

## Pruebas de carga (TP de test de carga y stress)

Los scripts en `tests/stress/` reproducen las dos pruebas con las que la cátedra compara las entregas. Pegan contra `POST /extract` a través de Traefik, con las 5 réplicas levantadas.

| Prueba | Script | Perfil | Envío del PDF |
|--------|--------|--------|---------------|
| Spike (modelo cerrado) | `k6-spike.js` | 0 → 100 VUs en 10 s, 20 s a 100 VUs, 100 → 0 en 10 s | multipart (`file`) |
| Carga fija (modelo abierto) | `vegeta-constant.sh` | 50 req/s durante 30 s (1.500 pedidos), timeout 30 s | body binario |

Las dos pruebas rotan en orden los 4 PDFs de `tests/stress/pdfs/`, así cada corrida manda la misma mezcla.

### PDFs de prueba

Se generan con un script en lugar de usar documentos reales: el set es reproducible (semilla fija, mismos archivos byte a byte) y no tiene problemas de derechos de autor.

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
docker run --rm -v "$PWD/tests/stress:/scripts"   -e BASE_URL=http://host.docker.internal:8000   grafana/k6 run /scripts/k6-spike.js

# Carga fija con Vegeta (imagen de la comunidad peterevans/vegeta)
docker run --rm -v "$PWD/tests/stress:/scripts"   -e BASE_URL=http://host.docker.internal:8000   --entrypoint sh peterevans/vegeta /scripts/vegeta-constant.sh
```

En Git Bash (Windows) hay que anteponer `MSYS_NO_PATHCONV=1` y usar `$(pwd -W)` en lugar de `$PWD`, para que no se reescriban las rutas del contenedor.

- `BASE_URL` apunta al servicio. `host.docker.internal` es la máquina anfitriona vista desde el contenedor.
- El script de Vegeta acepta además `RATE`, `DURATION` y `TIMEOUT` (por defecto, `50`, `30s` y `30s`).
- El script de k6 comparte una sola copia de los PDFs entre los 100 VUs (`k6/experimental/fs`). Con el `open()` clásico cada VU tendría su propia copia: unos 1 GB de RAM.

Las salidas de cada medición se guardan en `tests/stress/results/`, nombradas por prueba, motor de extracción y cantidad de réplicas.

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
| Pruebas de carga        | Grafana k6, Vegeta     |
