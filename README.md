# Extractor Service

Microservicio independiente para **extracción de texto desde archivos PDF**, construido con FastAPI y [`pypdf`](https://pypi.org/project/pypdf/).

Forma parte de una arquitectura de microservicios más amplia: es un servicio aislado, sin dependencias de otros servicios, que expone una API RESTful asíncrona para recibir un PDF y devolver su texto junto con metadatos de la extracción (páginas, tamaño, tiempo de procesamiento).

## Características

- API asíncrona con **FastAPI**.
- Extracción de texto con **pypdf**, corrida en un thread aparte para no bloquear el event loop.
- Contratos de entrada/salida tipados con **Pydantic** (validación de content-type, tamaño máximo y archivo vacío).
- Arquitectura en capas: endpoints HTTP, lógica de negocio y esquemas están desacoplados entre sí (principios SOLID/KISS/DRY/YAGNI).
- Suite de tests con **pytest**, desarrollada bajo un enfoque TDD, con PDFs generados en memoria de distintos tamaños (1, 10 y 100 páginas).
- Listo para contenedores: `Dockerfile` optimizado y `docker-compose.yml` propio del servicio.

## Arquitectura del proyecto

```
pdf-extract-service/
├── app/
│   ├── main.py                       # Application factory (FastAPI) + /health
│   ├── core/
│   │   └── config.py                 # Configuración vía variables de entorno
│   ├── exceptions.py                 # Excepciones de dominio (agnósticas de HTTP)
│   ├── schemas/
│   │   └── extraction.py             # DTOs Pydantic: entrada y salida
│   ├── services/
│   │   └── pdf_extractor.py          # Lógica de negocio: extracción con pypdf
│   └── api/
│       ├── error_handlers.py         # Traduce excepciones de dominio -> HTTP status
│       └── v1/
│           ├── router.py
│           └── endpoints/
│               └── extraction.py     # POST /api/v1/extract
├── tests/
│   ├── conftest.py                   # Fixtures: PDFs válidos generados en memoria
│   ├── test_pdf_extractor_service.py # Tests unitarios de la lógica de negocio
│   ├── test_schemas.py               # Tests del contrato de entrada
│   └── test_extraction_endpoint.py   # Tests de integración del endpoint HTTP
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── requirements-dev.txt
└── pytest.ini
```

**Principio de diseño:** el endpoint HTTP no conoce la lógica de extracción, y el servicio de extracción no conoce HTTP. Se comunican mediante excepciones de dominio (`app/exceptions.py`), que `app/api/error_handlers.py` traduce a códigos de estado HTTP. Esto mantiene la lógica de negocio reutilizable fuera del contexto web.

## Requisitos previos

- Python **3.12+**
- Docker y Docker Compose (opcional, para correr en contenedor)

## Instalación y entorno virtual

### Windows (PowerShell)

```powershell
# Crear el entorno virtual
python -m venv .venv

# Activarlo
.venv\Scripts\Activate.ps1

# Instalar dependencias de desarrollo (incluye las de producción + pytest)
pip install -r requirements-dev.txt
```

> Si `Activate.ps1` falla por política de ejecución de scripts, corré `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` y volvé a intentar.

### Linux / macOS / Git Bash

```bash
python3 -m venv .venv
source .venv/bin/activate      # Git Bash en Windows: source .venv/Scripts/activate
pip install -r requirements-dev.txt
```

### Variables de entorno

Copiá el archivo de ejemplo y ajustá los valores si hace falta (los defaults ya son válidos para desarrollo local):

```bash
cp .env.example .env
```

| Variable                | Descripción                                   | Default                  |
|--------------------------|-----------------------------------------------|---------------------------|
| `APP_NAME`               | Nombre de la aplicación                       | `extractor-service`       |
| `APP_VERSION`            | Versión expuesta en `/docs`                   | `0.1.0`                   |
| `HOST`                   | Host donde escucha uvicorn                    | `0.0.0.0`                 |
| `PORT`                   | Puerto donde escucha uvicorn                  | `8000`                    |
| `MAX_FILE_SIZE_MB`       | Tamaño máximo de PDF aceptado (MB)            | `10`                      |
| `ALLOWED_CONTENT_TYPES`  | Content-types aceptados (lista JSON)          | `["application/pdf"]`     |
| `LOG_LEVEL`              | Nivel de logging                              | `INFO`                    |

## Levantar el servicio localmente

Con el entorno virtual activado:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Documentación interactiva (Swagger UI): http://localhost:8000/docs
- Documentación alternativa (ReDoc): http://localhost:8000/redoc
- Health check: http://localhost:8000/health

### Ejemplo de uso del endpoint

```bash
curl -X POST http://localhost:8000/api/v1/extract \
  -F "file=@/ruta/a/documento.pdf;type=application/pdf"
```

Respuesta esperada:

```json
{
  "text": "contenido extraído del PDF...",
  "metadata": {
    "filename": "documento.pdf",
    "size_bytes": 24531,
    "page_count": 3,
    "processing_time_ms": 12.4
  }
}
```

Códigos de error posibles: `400` (archivo vacío), `415` (content-type no soportado), `413` (archivo supera el tamaño máximo), `422` (el archivo no es un PDF válido/parseable).

## Correr los tests (pytest)

Con el entorno virtual activado y las dependencias de `requirements-dev.txt` instaladas:

```bash
pytest
```

Modo verboso:

```bash
pytest -v
```

Con reporte de cobertura:

```bash
pytest --cov=app --cov-report=term-missing
```

Correr solo un archivo o clase de tests puntual:

```bash
pytest tests/test_pdf_extractor_service.py -v
pytest tests/test_extraction_endpoint.py::TestExtractEndpointSuccess -v
```

Los fixtures en `tests/conftest.py` generan PDFs válidos en memoria (no hay binarios versionados), lo que permite cubrir distintos tamaños de archivo:

- `small_pdf_bytes` → 1 página
- `medium_pdf_bytes` → 10 páginas
- `large_pdf_bytes` → 100 páginas
- `corrupted_pdf_bytes` / `not_a_pdf_bytes` / `empty_file_bytes` → casos inválidos

## Uso con Docker Compose

1. Asegurate de tener un archivo `.env` (copiado desde `.env.example`):

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
docker run --rm -p 8000:8000 --env-file .env extractor-service:latest
```

El contenedor corre como usuario no-root, expone el puerto `8000` y define un `HEALTHCHECK` contra `/health`.

## Stack técnico

| Componente         | Herramienta            |
|---------------------|-------------------------|
| Framework web        | FastAPI                |
| Servidor ASGI         | Uvicorn                |
| Extracción de PDF     | pypdf                  |
| Validación de datos   | Pydantic / pydantic-settings |
| Testing                | pytest, pytest-asyncio, httpx |
| Contenedores            | Docker / Docker Compose |
