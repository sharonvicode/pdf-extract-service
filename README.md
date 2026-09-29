# Extractor Service

Microservicio independiente para **extracción de texto desde archivos PDF**, construido con FastAPI y [`pypdf`](https://pypi.org/project/pypdf/).

Forma parte de una arquitectura de microservicios más amplia: es un servicio aislado, sin dependencias de otros servicios, que expone una API RESTful asíncrona para recibir un PDF y devolver su texto junto con metadatos de la extracción (páginas, tamaño, tiempo de procesamiento).

## Características

- API asíncrona con **FastAPI**.
- Extracción de texto con **pypdf**, corrida en un thread aparte para no bloquear el event loop.
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
│   │   └── pdf_extractor.py          # Lógica de negocio: extracción con pypdf
│   └── api/
│       ├── error_handlers.py         # Traduce excepciones -> respuestas RFC 9457
│       └── v1/
│           ├── router.py
│           └── endpoints/
│               └── extraction.py     # POST /api/v1/extraer
├── tests/
│   ├── conftest.py                   # Fixtures: PDFs válidos generados en memoria
│   ├── test_pdf_extractor_service.py # Tests unitarios de la lógica de negocio
│   ├── test_schemas.py               # Tests del contrato de entrada
│   ├── test_extraction_endpoint.py   # Tests de integración del endpoint HTTP
│   └── test_problem_details.py       # Tests del formato de errores RFC 9457
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

1. (Opcional) Si querés cambiar algún valor por defecto, creá un `.env` a partir de `.env.example` y editalo. Sin `.env` el servicio usa los valores por defecto:

   ```bash
   cp .env.example .env
   ```

2. Levantar el servicio:

   ```bash
   docker compose up --build
   ```

3. El servicio queda disponible en `http://localhost:8000` (o el puerto que definas en `PORT`).

4. Para correrlo en segundo plano:

   ```bash
   docker compose up -d --build
   ```

5. Para detenerlo:

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

## Stack técnico

| Componente         | Herramienta            |
|---------------------|-------------------------|
| Framework web        | FastAPI                |
| Servidor ASGI         | Uvicorn                |
| Extracción de PDF     | pypdf                  |
| Validación de datos   | Pydantic / pydantic-settings |
| Testing                | pytest, pytest-asyncio, httpx2 |
| Dependencias           | uv                     |
| Contenedores            | Docker / Docker Compose |
