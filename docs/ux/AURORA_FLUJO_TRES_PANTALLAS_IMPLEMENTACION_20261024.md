# AURORA Professional · Cierre quirúrgico del flujo de tres pantallas (24/10/2026)

## Base de trabajo
PR #20 remoto `acb6b3d759e1b6d93dffb8b3c156f2332371c1b6`. Esta rama **no contiene todavía** los commits locales Antigravity `c815d0c` ni la rama local `integration/aurora-corporate-final-20261023` notificada, al no estar publicados en GitHub.

## Flujo funcional implementado en esta rama
### 1. Inicio
- `BundleSelectionPanel.jsx`: selección por casillas de **estudios OPEN de una empresa ya configurada**; solo públicos, con versión instrumental y no vencidos, sin invitación obligatoria. De 2 a 12.
- Se crea una batería real mediante `POST /projects/{project_id}/bundles`; se exhibe enlace público y QR. Solo OWNER/ADMIN según guardias del backend.
- El catálogo histórico se oculta por defecto cuando la empresa ya tiene evaluaciones y se abre con «Explorar catálogo»; evita el carro fijo que tapaba contenido.
- **Limitación contractual:** marcar una versión de catálogo no provisiona automáticamente una campaña nueva. Primero debe existir un estudio OPEN; automatizar su creación de forma atómica requiere definir reglas por metodología, baremos y autorizaciones de publicación. No se simula como funcionalidad terminada.
### 2. Batería pública
- `/bateria/{uuid}` inicia la primera encuesta y, al completarse exitosamente, avanza al siguiente instrumento **en la misma página y sin abrir pestañas**.
- Cada encuesta inicia sesión anónima diferente con el API existente, sin un ID transversal de trabajador; conserva ítems, autorización y scoring independientes.
- Se consulta otra vez el endpoint público antes de avanzar; una batería revocada o un estudio cerrado bloquea los siguientes.
- No se persiste una identidad global ni se declara una matriz de correlaciones entre respuestas individuales de distintos instrumentos.
- La continuidad es en memoria mientras está abierta la pestaña; **recargar reinicia el asistente**. Debe probarse antes de uso masivo y definir recuperación de sesión sin reidentificación para una fase posterior.
### 3. Telemetría
- Se retiró una segunda cabecera con breadcrumbs y el bloque extra «Aplicación/Estudio»: un solo selector de estudio, actualizar, pausar y gestionar.
- `ExecutiveDecisionBoard`: diagnóstico/matriz, mapa de calor y evolución en **el mismo espacio**, filtrando por dimensión y unidades publicables. El mapa muestra porcentajes devueltos por el servidor, no reclasifica baremos.
- Los KPI no muestran falso valor 0 cuando no existen dimensiones publicables.
- Filtros simultáneos multivariables entre sexo/turno/sede **no se afirman como implementados**. Requieren agregados del backend con supresión antiinferencia.
### 4. Informe
- El visor/constructor es la función principal; la opción de consolidación de batería solo monta el componente al abrir «Informe de batería». No aparece error de baterías delante del visor.
- Los PDFs definitivos siguen exigiendo orden pagada consumida y validación SHA-256 de origen.
- La compilación ahora añade **una portada ejecutiva corporativa e índice**, con dos indicadores documentales verificables: número de instrumentos y número de informes autorizados. Marcadores y paginación de fuentes conservados en manifiesto.
- **No** se calcula un supuesto riesgo global ni se mezclan escalas de métodos diferentes. Los hallazgos sustantivos siguen en las secciones propias de cada informe. Para comparaciones multimetodología hace falta una especificación estadística autorizada.

## Evidencias requeridas antes de aprobar en Windows
- Ejecutar `npm ci && npm run lint && npm run test && npm run build`.
- `poetry run pytest -q app/tests`, `poetry run alembic current`, upgrade aislado PostgreSQL 16.
- End-to-end real: dos estudios publicados, un enlace `/bateria/uuid`, responder sucesivamente, revocar a mitad, comprobar separación de sesiones y datos, filtros en BI, PDF de origen pagado y consolidado con portada.
- Verificar 360×800, 768×1024, 1440×900; comprobar scroll del canvas, la ausencia del carrito flotante y que Informe abra en el visor.
- Reconciliar con trabajo local Antigravity. No duplicar controles ni crear una segunda pantalla para la misma función.
- Revisar que los PDF y valores numéricos por instrumento coinciden con el scoring del backend.

## Decisión de aceptación
El CI de esta rama **no equivale** a QA de navegador en la instalación local. El PR es draft hasta la validación de la rama unificada. No fusionar `main` ni habilitar datos reales sin aprobación.
