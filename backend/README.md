> **AURORA Professional:** la documentación histórica de Colmena puede
> describir autenticación o PDF anteriores. Para la versión actualizada,
> consulta [estado profesional](../docs/AURORA_PROFESSIONAL_STATUS.md),
> [validación metodológica](../docs/VALIDACION_METODOLOGICA.md) y
> [operación](../deploy/OPERATIONS.md). El despliegue con datos reales
> requiere el control de calidad descrito en esos archivos.

# Colmena Backend

Backend unificado de Colmena (proyectos académicos + CENSOPAS-COPSOQ + surveys + motor estadístico).

Implementa **todas las fases (1-9)** de `../CODEX_HARNESS_COLMENA_BACKEND.md`:

- **Fase 1 (Core)**: proyectos, instrumentos, versiones de instrumento, preguntas, option sets, constructos (dimensiones/subdimensiones), variables.
- **Fase 2 (Editor)**: CRUD completo — variables, dimensiones/subdimensiones, ítems, asignación ítem↔constructo, edición batch, árbol de instrumento, matriz, clonar/versionar instrumento. Bloqueo de edición (`InstrumentEditPolicy`) por estado de versión, instrumento `is_system` y estudios `OPEN` referenciando la versión.
- **Fase 3 (Surveys)**: surveys libres o creados desde instrumento (sin duplicar ítems), estudios con ciclo de vida `DRAFT → OPEN → CLOSED → ARCHIVED` (con snapshot inmutable al abrir), sesiones de respuesta anónimas y captura de respuestas en formato largo.
- **Fase 4 (Dataset)**: `DatasetService` — dataset largo/ancho (pivot dinámico, sin duplicar físicamente), diccionario de variables (`/studies/{id}/data-dictionary`), helpers de filtros y supresión por `min_publishable_n`.
- **Fase 5 (Analytics básicos)**: motor estadístico síncrono (`app/analytics/`) con DESCRIPTIVE, FREQUENCIES y CROSSTAB; cada ejecución crea un `analysis_run` (PENDING→RUNNING→COMPLETED/FAILED) con `analysis_results` persistidos; descubrimiento vía `/analytics/methods` y `/studies/{id}/analytics/available-methods`; despacho genérico `/studies/{id}/analysis-runs` + `/analysis-runs/{id}`.
- **Fase 6 (CENSOPAS)**: `app/analytics/censopas/` (scoring por ítem con `raw_code`→`score_0_100`, agregación ponderada con dirección REVERSE, clasificación por barem, regla colectiva configurable §30), `PrivacyService` (supresión por `min_publishable_n`), CRUD de `scoring_rules`/`barems`/`barem_cutoffs`, `CensopasScoringService.run_scoring` + `/studies/{id}/censopas/results` con privacidad aplicada.
- **Fase 7 (Inferencial)**: chi-cuadrado, Mann-Whitney/Kruskal-Wallis (auto-dispatch por número de grupos), Spearman, alfa de Cronbach, omega de McDonald (aproximación unifactorial vía PCA — no CFA completo), corrección Benjamini-Hochberg (utilidad testeada, sin endpoint batch dedicado todavía). Validación de supuestos por `measurement_level` (`InvalidAnalysisAssumptionError`) y tamaño muestral (`InsufficientSampleError`).
- **Fase 8 (Exports)**: CSV, XLSX (openpyxl), JSON — long/wide dinámico. **SPSS/PowerBI/Parquet no implementados** (requieren pyreadstat/polars, no instalados; fallan con un error de dominio claro, no silenciosamente).
- **Fase 9 (Avanzado)**: regresión logística (IRLS vía numpy) y k-means (Lloyd vía numpy) — sin scikit-learn. BSC completo (`action_plans`, `action_plan_items`, `kpis`, `kpi_measurements`). `ReportService` ensambla un *bundle* (estudio + resultados de análisis + `barem_results`) y lo renderiza a **Word (.docx, default)** vía `report_docx.py` — ficha técnica, tabla de baremación por dimensión (con celdas coloreadas según `color_hint` de cada banda) y dos gráficas embebidas (matplotlib, backend "Agg"): distribución de bandas y puntaje promedio por prioridad. `output_format=JSON` se conserva para integraciones que quieran el bundle crudo. PDF sigue sin implementarse.
- **Auth propia + CORS**: `POST /auth/register`, `POST /auth/login` (bcrypt + JWT vía PyJWT), `GET /auth/me`. Añadido para soportar el frontend standalone (`../frontend`) — el harness original asumía SSO externo desde AppThesis, que no existe en este proyecto. `CORSMiddleware` habilitado para `http://localhost:5174` (ver `Settings.cors_origins`).

Todo lo anterior corre **síncronamente** (sin Celery/Redis): frecuencias, descriptivos, inferencial, reliability, regresión y k-means son computacionalmente ligeros en los volúmenes de esta fase. El harness reserva colas reales para trabajos verdaderamente pesados a mayor escala — no se implementó esa infraestructura todavía.

## Limitaciones documentadas (no simulan estar completas)

- **Exports**: SPSS/PowerBI/Parquet devuelven `422 VALIDATION_ERROR` explícito en vez de generar un archivo incorrecto.
- **Reportes**: `output_format=DOCX` (default) o `JSON`; PDF sigue sin implementar (requeriría reportlab/weasyprint u otra librería de maquetación adicional).
- **McDonald's omega**: aproximación de un solo factor (PCA sobre la matriz de correlación), no un modelo CFA robusto.
- **Regresión logística**: sólo predictores numéricos (SCALE/ORDINAL); no codifica variables categóricas como dummies.
- **Benjamini-Hochberg**: la función `adjust_pvalues_bh` existe y está testeada, pero no hay todavía un endpoint que ejecute múltiples pruebas relacionadas y aplique la corrección automáticamente.
- **Autorización**: existe login/registro reales (JWT), pero los ~15 routers de negocio (projects/instruments/surveys/etc.) siguen aceptando `owner_user_id`/`created_by_user_id` explícito en el body en vez de derivarlo del token — no hay retrofit de autorización por endpoint todavía. `GET /auth/me` sí está protegido con `get_current_user`.

## Requisitos

- Python 3.12+
- PostgreSQL 15+
- [Poetry](https://python-poetry.org/)

## Setup

```bash
cd backend
poetry install
cp .env.example .env   # ajustar DATABASE_URL
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

La API queda disponible en `http://localhost:8000`, con documentación interactiva en `/docs`.

## Seed de dos usuarios CensoPÁS

El seed idempotente instala el catálogo oficial si hace falta y crea dos
cuentas demo, cada una con su propia organización y proyecto: Ana usa el plan
corto y Carlos el plan medio.

```bash
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python scripts/seed_two_censopas_users.py
```

Ambas cuentas usan la contraseña `ColmenaDemo2026!`:

- `ana.torres@censopas.demo`
- `carlos.mendoza@censopas.demo`

## Tests

```bash
poetry run pytest
```

92 casos recolectados (unit + integración, incluidos casos parametrizados). Los tests de integración usan SQLite en memoria (`aiosqlite`) por defecto para no requerir Postgres. Cada fase fue además verificada manualmente contra un Postgres 16 real (contenedor Docker desechable) corriendo la migración completa y ejercitando los flujos end-to-end vía `curl`.

## Estructura

Ver `../CODEX_HARNESS_COLMENA_BACKEND.md` §4 para el árbol completo objetivo. Este repo lo implementa completo, con la estructura `app/analytics/` (incluido `app/analytics/censopas/`) separada de `app/services/` tal como pide §4 ("no colocar lógica estadística compleja directamente en routers FastAPI").
