# AURORA Professional: experiencia empresarial de tres pantallas

Base aprobada en la reunión del 21 de octubre de 2026. Implementación incremental en `feat/aurora-three-screen-ux-20261021`, PR #18 contra PR #17. **No fusionar automáticamente con main.**

## 1. Inicio

- Catálogo CENSOPAS y catálogo multidisciplinario consultados desde la API.
- Tarjetas densas con estado real de instrumento, metadatos básicos y acciones visibles.
- Mis evaluaciones: cambio rápido de expediente hacia Telemetría e Informe.
- Generación de evaluación rápida existente y flujo de proyectos empresariales reutilizados.
- Creación de una batería a partir de 2 a 12 estudios ya configurados, abiertos y públicos en la pantalla auxiliar de enlaces.
- La batería tiene UUID público, selección de estudios, QR, auditoría y revocación. Su landing muestra vínculos separados para cada encuesta.
- Los estudios que exigen invitación individual **no** se agregan a una batería pública. No se anulan tokens ni permisos.

**Límite real:** la batería comparte un enlace de entrada, no crea todavía una sesión continua con identificador anónimo común. No calcula automáticamente la cotización unificada. Los reportes y baremos siguen separados por estudio.

## 2. Telemetría y diagnóstico

- Navegación única desde proyecto y móvil.
- Cabecera ejecutiva, selección de campaña, autoactualización de captura y botón de pausa.
- `PremiumBIWorkspace` con cuadros seleccionables: indicadores, distribución, ranking, segmentos, hallazgos, evolución y plan de acción.
- Gráficos alternativos para CENSOPAS: barras horizontales apiladas, tarjetas compactas y mapa de calor basado en porcentaje desfavorable. El mapa no crea umbrales de riesgo adicionales.
- Estadística CENSOPAS: la API proporciona porcentaje favorable, intermedio y desfavorable; React no recalcula baremos.
- Instrumentos genéricos: puntajes descriptivos normalizados en lugar de categorías de riesgo inventadas.
- Selección de dimensión actualiza los cuadros; filtros de tipo de unidad y unidad consumen resultados segmentados del servidor.
- Las celdas suprimidas no aparecen en selector, ranking ni visuales; se conserva la protección de unidades pequeñas y secundaria.
- La vista segmentada no hereda recomendaciones generales como si fueran conclusiones del segmento.
- Comparación longitudinal del backend: solo curvas metodológicamente compatibles; el sistema no une mediciones no equivalentes.
- Seguimiento de intervenciones, con avance de planes basado en estados existentes de la API.
- Drag and drop más controles de orden accesibles, alternancia de densidad y personalización de cuadros.
- Preferencias visuales por usuario y empresa en `/api/v1/dashboard-preferences/{organization_id}` con comprobación de pertenencia; almacenamiento en metadata sin respuestas de trabajadores.

**Límites reales:** no se han implementado filtros simultáneos cruzando sexo, edad, turno y área como un motor OLAP; requieren backend con umbrales de divulgación y protección antiinferencia. El heatmap es por dimensión, no por matrices multidimensionales.

## 3. Informe

- Página principal con prioridad al visor PDF y configuración secundaria.
- Motor DOCX/PDF existente preservado, con paleta AURORA y visualizaciones ejecutivas adicionales.
- KPI gráficos sobre datos previamente procesados y ranking en gráfico de porcentaje desfavorable, sin modificar el scoring.
- Plantillas personalizables, portada de empresa, tablas técnicas, interpretaciones, firmas y trazabilidad conservadas.
- Generación de muestra marcada sin validez oficial, descarga autorizada de informes y control de órdenes pagadas.
- Para cuentas expresamente etiquetadas en el servidor `user.metadata.aurora_demo_one_report=true`, la primera emisión de muestra reserva un crédito de forma atómica (0026). Un error de render devuelve la reserva. Los demás administradores pueden seguir usando vistas de muestra bajo las políticas comerciales existentes.
- Consolidación de batería: reúne **exclusivamente** el último PDF definitivo pagado y con orden `CONSUMED` de cada estudio; valida SHA-256 de cada origen, dominio empresarial y límites de tamaño. Genera un PDF con marcadores y manifiesto de documentos fuente, historial y descarga protegida.
- El visor consolidado se abre dentro de Informe, en pestaña o pantalla completa. El resumen metodológico de cada instrumento permanece en su documento original.

**Límites reales:** la cuota de demo es por **cuenta habilitada**, no garantiza una persona física única entre diferentes cuentas. Para esa garantía hace falta verificación de identidad que aún no está implementada. El consolidado PDF reúne documentos individuales ya pagados, no genera todavía una portada ejecutiva analítica multimetodología ni certifica o firma digitalmente la compilación. No sustituye originales.

## 4. Seguridad y trazabilidad

- Aislamiento por empresa en preferencias, baterías e informes.
- Asociación de estudios al proyecto y consulta pública limitada a estudios habilitados.
- Historial de revocaciones y emisiones por auditoría.
- Cuota demo protegida con clave única y control de concurrencia.
- Informe consolidado exige orden pagada consumida; nunca utiliza muestras ni archivos sin hash correcto.
- Los resultados omitidos por privacidad permanecen omitidos al filtrar.
- Se conserva la distinción entre muestra no oficial e informe autorizado. No atribuir acreditación a SUNAFIL/CENSOPAS automáticamente.

## 5. Migraciones nuevas

- `0025_evaluation_bundles.py`: enlaces de batería revocables.
- `0026_demo_report_entitlement.py`: consumo único de muestra por cuenta demo autorizada.
- `0027_consolidated_bundle_reports.py`: historial y manifiesto de PDFs consolidados.

**Despliegue:** respaldar base y almacenamiento, restaurar en entorno de prueba, ejecutar `poetry run alembic upgrade head`, verificar índices, roles, licencias y funcionalidad. No migrar sobre datos reales sin respaldo y rollback.

## 6. Pruebas y puerta de entrega

`.github/workflows/aurora-bi-release-checks.yml` ejecuta:
- `npm ci`, `npm run lint`, `npm run test` y `npm run build`.
- Python `compileall`, suite `pytest` completa con motor LibreOffice.
- Migraciones reales en PostgreSQL 16 temporal hasta `0027`.

Además validar manualmente en Windows, Chrome/Brave y móviles de 360, 768 y 1440px:
- Entrada a tres pantallas, navegación entre 2 empresas, campañas y sesiones.
- 7 cuadros seleccionables, persistencia por cuenta y empresa, cambio de visualizaciones y accesibilidad por teclado.
- Filtros por unidades, supresión primaria/secundaria y ninguna inferencia de grupos pequeños.
- Enlace de batería: 2 estudios, revocación, status OPEN/CLOSED, cuestionarios separados, no saltar invitaciones.
- Demo: primer informe de muestra autorizado, segundo denegado, fallo de render con crédito recuperable.
- PDF final: orden pagada para cada informe fuente, hash válido, consolidación de fuentes PDF, manipulación detectada, previsualización y descarga.
- Análisis estadístico contrastado contra fuente independiente; firmas profesionales y equivalencia metodológica comprobadas.
- Rendimiento: muestras sintéticas de 100, 500 y 1000 participantes, p95, CPU/RAM, generación de documentos y tiempo de carga por filtro.
- Accesibilidad WCAG 2.2 AA como objetivo de aceptación, no certificación automática.

## 7. Trabajo no declarado como cerrado

- Sesión continua de batería y cálculo integrado de cotización.
- Filtros multinivel cruzados por atributos demográficos con análisis antirreidentificación.
- Informe ejecutivo consolidado de metodologías distintas con portada propia.
- Verificación de persona única para demo, más allá de la cuenta autenticada.
- Firma digital oficial y evaluación de requisitos normativos por especialistas.
- Pruebas completas sobre infraestructura de producción, hardware local y Cloudflare Tunnel.
- Capacitación asincrónica offline y certificados QR, que todavía deben diseñarse como módulo independiente.

El estado final del PR requiere CI verde, prueba local con backup y aprobación metodológica, técnica y comercial.
