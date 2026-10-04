# TP Test de Carga y Stress — Objetivos del Extractor

Entrega: 07/10/2026. Marca a superar (profesor):

| Prueba | Throughput | Éxito | p50 | p95 |
|---|---|---|---|---|
| k6 spike (100 VUs, 10s/20s/10s) | 25.35 req/s | 100% | 1.88 s | 8.80 s |
| Vegeta (50 req/s × 30 s, timeout 30 s) | 16.65 req/s | 66.53% | 14.89 s | — |

## Fase 1 — Contrato del TP
- [x] `POST /extract` (multipart) → `200 {"content", "page_count"}`
- [x] Aceptar también el PDF como body binario directo
- [x] Test de regresión: multipart sin campo `file` → 422 (no 500)
- [ ] Aplicar en `/extract` el límite de tamaño (413) que ya tiene `/api/v1/extraer`

## Fase 2 — Infraestructura
- [ ] Reverse proxy (Traefik o Caddy) delante del Extractor
- [ ] `deploy.replicas: 5` con límites explícitos de CPU y RAM por réplica
- [ ] Todo levanta con `docker compose up --build`

## Fase 3 — Medición inicial ("antes")
- [ ] Set propio de 4 PDFs en `tests/stress/pdfs` (liviano, mediano, largo, ~9 MB con gráficos)
- [ ] Script k6 (spike) en `tests/stress/`
- [ ] Script Vegeta (50 req/s × 30 s) en `tests/stress/`
- [ ] Resultados con pypdf registrados

## Fase 4 — Optimización (medir después de cada cambio)
- [ ] Migrar a PyMuPDF + pymupdf4llm (`content` en Markdown)
- [ ] Backpressure: límite de concurrencia y 503 + `Retry-After`
- [ ] Ajuste de workers por réplica

## Fase 5 — Informe
- [ ] Arquitectura y decisiones de diseño
- [ ] Cuello de botella identificado
- [ ] Comparativa antes vs. después vs. profesor
- [ ] Proceso de investigación
