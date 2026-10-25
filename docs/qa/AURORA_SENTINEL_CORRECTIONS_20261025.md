# AURORA Sentinel Correcciones y puerta de validación

Fecha: 25 de octubre de 2026. Base auditada: `ef41741cbe6812b8bc0b867646d346579a438768`.
Rama: `fix/aurora-authentic-results-20261025`. Destino: PR en borrador hacia integración; no merge ni despliegue.

## Dictamen

**Código de corrección para validación, no aceptación comercial.** Ningún resultado de pruebas aisladas sustituye la comprobación del entorno empresarial. La retirada de credenciales del HEAD no revoca credenciales ni limpia el historial. No se ha utilizado una credencial publicada.

## Separación de evidencia

- Implementado en código: consultar diff y tests añadidos del PR.
- Automático: el resumen final abajo registra la suite del árbol integrado; CI quedará ligado al SHA del PR.
- Navegador real: pendiente. El servidor aislado no fue accesible desde el navegador; `file://` fue rechazado por la política de navegación. No se eludieron restricciones.
- Base de datos: pruebas de integración con SQLite aislado. Migración PostgreSQL 16 se ejecutará en CI; no representa validación operativa de Windows.
- PDF: pruebas de conversión real con LibreOffice, contenido de una corrida histórica y consolidación; no se inspeccionó un PDF de cliente ni se comparó con navegador real.
- Pendiente o fallido: indicado por requisito; no se declaran 36 cierres.

## Matriz de las 36 observaciones

| ID | Prioridad | Requisito | Estado de corrección y límite |
|---|---|---|---|
| AUR-01 | P0 | Ningún KPI o porcentaje ficticio en ruta productiva | CORREGIDO EN CÓDIGO + tests visibles; navegador real pendiente |
| AUR-02 | P0 | Filtros visibles deben cambiar datos reales o figurar inhabilitados | FILTROS REALES dimensión/tipo/unidad; cruces no soportados no se simulan |
| AUR-03 | P0 | Prohibido contar dimensiones de alto riesgo como personas de alto riesgo | CORREGIDO: no se presentan dimensiones como personas |
| AUR-04 | P0 | No filtrar/gráficar datos suprimidos ni permitir reidentificación | PARCIAL: supresión y guardas de corrida conservadas; aceptación de privacidad completa pendiente |
| AUR-05 | P0 | Eliminar credenciales de ejemplo expuestas y rotarlas | PARCIAL P0: retiradas credenciales del código; rotación e historial pendientes; descripción pública del PR 22 saneada |
| AUR-06 | P0 | Clasificación y recomendaciones metodológicamente fundamentadas | PARCIAL: contexto de scoring/baremo; revisión metodológica profesional pendiente |
| AUR-07 | P1 | Inicio: seleccionar instrumentos **del catálogo** directamente con checkbox | CORREGIDO + tests: catálogo directo con casillas, versión/empresa, apertura validada, enlace/QR; navegador pendiente |
| AUR-08 | P1 | Un solo enlace/QR y batería ordenada | IMPLEMENTADO + pruebas automáticas; QR móvil pendiente |
| AUR-09 | P1 | Responder instrumentos sucesivamente en una URL | IMPLEMENTADO + pruebas automáticas; flujo navegador completo pendiente |
| AUR-10 | P1 | Recuperar el progreso ante recarga o desconexión | CORREGIDO + pruebas de recarga, reintento y vencimiento; sesión de pestaña, no entre dispositivos |
| AUR-11 | P1 | Soportar elección de un solo instrumento con enlace | CORREGIDO + pruebas: un instrumento produce enlace individual |
| AUR-12 | P1 | Revocación y expiración del enlace | IMPLEMENTADO: revocación bloquea entrada y transición; no borra respuestas registradas |
| AUR-13 | P1 | Inicio sin banner de demo dominante, carrito flotante ni duplicación | CORREGIDO EN CÓDIGO: retirado banner con IDs y cifras fijos; captura pendiente |
| AUR-14 | P1 | Navegación corporativa solo Inicio/Telemetría/Informe | NO VALIDADO EN NAVEGADOR: conservar tres pantallas primarias |
| AUR-15 | P1 | Transiciones suaves sin efecto sobre rendimiento | NO VALIDADO: movimiento reducido y rendimiento visual en dispositivos |
| AUR-16 | P1 | Tablero BI compacto visible en viewport 1440×900 | NO VALIDADO: revisión visual 1440 por 900 bloqueada por entorno de navegador |
| AUR-17 | P1 | Matriz, barras, donut, calor, evolución, ranking basados en servidor | CORREGIDO EN CÓDIGO + aserciones de geometría visible y fuentes |
| AUR-18 | P1 | Comparación cruzada múltiple (sexo/turno/sede/etc.) | PARCIAL: no existe nuevo motor de intersecciones sexo por turno por sede; no se simula |
| AUR-19 | P1 | Panel gerencial explica dimensión y acción sin leer preguntas | PARCIAL: interpretación desde backend, sin relatos temporales inventados; aceptación por especialista pendiente |
| AUR-20 | P1 | `Sin datos` y `N/D` no se reemplazan por `0`, `18` o `28` | CORREGIDO + tests: cero real distinto de N/D, error y supresión |
| AUR-21 | P1 | Contexto empresa/estudio consistente; sin título minero fijo | CORREGIDO + tests: empresa/estudio reales, sin mina fija |
| AUR-22 | P1 | Evolución solo con versión y baremo comparable | CORREGIDO + tests: comparabilidad, huecos y rangos válidos |
| AUR-23 | P1 | Informe muestra vista previa antes que consolidación o errores | IMPLEMENTADO + invalidación de preview ante cambio de corrida; navegador pendiente |
| AUR-24 | P1 | PDF coherente de batería con portada, índice y anexos separados | IMPLEMENTADO + tests de consolidación, fuentes y portada; revisión PDF cliente completa pendiente |
| AUR-25 | P1 | Los indicadores ejecutivos del PDF deben ser sustantivos | MEJORADO: N scoring e indicador por instrumento con fuente; sin índice global |
| AUR-26 | P0 | Paridad visible entre Telemetría y PDF | PARCIAL: pinning y test PDF histórico real; contraste UI navegador contra PostgreSQL pendiente |
| AUR-27 | P1 | 1 demo acotada con autenticación segura | PARCIAL: fallback inseguro retirado; cuotas/credenciales vigentes pendientes |
| AUR-28 | P1 | Identidad AURORA Professional homogénea y tema blanco | CONSERVADO EN CÓDIGO; aceptación visual de marca y contraste pendiente |
| AUR-29 | P1 | Datos sintéticos claramente marcados; no mezclar 35/112/238 | CORREGIDO EN VISTA GENERAL: sin valores de maqueta; datos de ensayo explícitamente sintéticos |
| AUR-30 | P1 | QA E2E independiente sobre **último commit PR22** | PENDIENTE: evidencia navegador/Windows del SHA final; suites aisladas no equivalen a E2E operativo |
| AUR-31 | P1 | Backend / UI performance sin recargar datos ocultos | PENDIENTE: benchmark representativo y navegador Performance/Network |
| AUR-32 | P1 | Legalidad de instrumento/autoría, consentimiento y uso | PENDIENTE: evidencia de licencias, autoría, consentimiento y uso; no certificada por esta revisión |
| AUR-33 | P1 | Licenciamiento/headcount y pedidos consumidos para PDF oficial | CONSERVADO + tests: orden pagada, estudio/empresa, consumo y hash; pasarela real no probada |
| AUR-34 | P1 | Probar aislamiento con DOS empresas **existentes**, no solo ID inexistente | MEJORADO + tests: dos empresas existentes en DB aislada y QA fail-closed; instalación real pendiente |
| AUR-35 | P2 | Compactar hero y componentes Informe/Inicio, eliminar ruido | PARCIAL: menos ruido; validación visual cliente pendiente |
| AUR-36 | P2 | Responsivo móvil/tableta, transiciones y accesibilidad | PENDIENTE: responsive real, teclado y accesibilidad en navegador |

## Tres acciones de cierre

1. Validar el SHA integrado con suite completa, lint, build, controles de fuente y CI; conservar regresiones de datos visibles, corridas, privacidad y licencias.
2. Con permiso local: levantar en Windows en directorio y base aislados, sin sobrescribir ramas, `.env`, secretos, DB ni servicios. Probar catálogo a batería a respuestas a scoring a tablero a PDF con dos empresas de ensayo y captura del DOM visible.
3. Antes de empresas: rotar credenciales expuestas con autorización específica, sanear descripción/artefactos históricos sin reescritura destructiva, verificar derechos metodológicos, respaldos/restauración, disponibilidad y operación comercial.

## Evidencia automática final

Verificado sobre el árbol de corrección integrado el 25 de octubre de 2026, antes del commit de publicación:

- Frontend: 117/117 tests, 25 archivos. ESLint sin errores. Build Vite correcto.
- Backend: 358/358 tests en SQLite aislado, incluida conversión real LibreOffice y prueba PDF de corrida histórica. La suite final corrige dos incompatibilidades de texto del error de autorización, sin debilitar la validación.
- Seguridad de scripts y credenciales: 8/8 tests offline.
- Compilación Python y `git diff --check`: correctos.
- Revisión independiente del código: detectó y corrigió preview desactualizado por cambio de corrida, reintento de envío ambiguo, fingerprint de corrida suplementaria, selección revocada y paginación malformada.
- Ninguna dependencia de aplicación ni archivo lock se modificó. El instalador Poetry de CI quedó alineado al formato 2.1 del lock existente.
- La ejecución de CI y PostgreSQL debe consultarse en el SHA exacto del PR; estos resultados no se atribuyen a un SHA anterior ni a Windows.

## Correcciones principales

1. Un solo catálogo principal permite marcar versiones autorizadas, abrir campañas mediante las reglas del servidor y emitir enlace individual o batería ordenada; los bloqueos del método producen error explícito, nunca una URL ficticia.
2. Los gráficos visibles utilizan la misma fuente normalizada que sus datos accesibles. No hay tabla oculta como sustituto de una visualización real. Los filtros no implementados se muestran no disponibles.
3. Informes y recomendaciones se fijan a scoring, versión y baremo; cambios de corrida invalidan previews. Comparaciones segmentadas se ocultan ante diferencia de corrida. Los historiales sin fingerprint se identifican, no se certifican retroactivamente.
4. Autorización vigente se revalida al abrir, crear/consultar baterías, abrir encuesta pública y crear sesión. Métodos revocados no heredan un permiso perpetuo por conservar estado OPEN.
5. No se probaron credenciales expuestas ni se rotaron. Se retiró la línea de credenciales de la descripción del PR 22, sin cambiar sus afirmaciones históricas. No se reescribió historial, fusionó main ni desplegó.


## Comprobación de CI y reparación del entorno de pruebas

El primer CI del PR 23 sobre `393855af9eb244bf9bdb7c3905ddc81d650dbe90` ejecutó realmente los trabajos: frontend, controles de fuente y migración PostgreSQL 16 aprobaron. Backend: 355 PASS y 3 errores de preparación, no aserciones funcionales fallidas. El origen fue `--basetemp=tmp/pytest`: el directorio padre no existe en una copia nueva. Se retiró ese supuesto y se utiliza el directorio temporal gestionado por pytest. Ocho pruebas afectadas aprobaron en nube con configuración por defecto; `poetry check --lock` correcto, sin cambios del lock.

Run inicial: https://github.com/ammyt1010-spec/Aurora/actions/runs/40173940013 . El siguiente CI debe confirmar la suite completa de esta reparación. Las migraciones de CI no son prueba de despliegue Windows ni restauración operativa.
