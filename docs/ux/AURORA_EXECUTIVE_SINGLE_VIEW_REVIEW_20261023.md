# AURORA Professional | Revisión quirúrgica de densidad visual (23/10/2026)

## Base auditada
PR #18, commit remoto `b78c29bac1fbfa15702f522d5ae02c071d35c7e6`.
El commit local comunicado por el propietario, `c815d0c`, **aún no está publicado en GitHub** al crear esta rama. Esta corrección no reemplaza los cambios locales de Antigravity ni pretende auditarlos antes del push.

## Problemas concretos del código base
1. `PremiumBIWorkspace.jsx` representa siete cuadros por defecto. Varios repiten dimensiones, proporciones y prioridades y se suman verticalmente.
2. `TelemetryOverview.jsx` vuelve a introducir entre cinco y seis KPI, embudo, donut, evolución de captura y medidor de calidad. Es útil como detalle técnico, no como superficie gerencial principal.
3. `ProjectPremiumDashboardPage.jsx` contiene otra lectura paralela de aproximadamente 596 líneas, con cinco KPI, gráficas de exposición, prioridades, subdimensiones y secciones de pruebas avanzadas.
4. `ProjectResultsPage.jsx` ofrece 13 pestañas técnicas; no es una navegación adecuada como flujo predeterminado de gerencia.
5. La navegación selecciona empresa, campaña, dimensiones, unidad y estudio en distintos componentes. Se debe evitar que cada panel use un alcance diferente.
6. El pie de página y las descripciones repetidas consumen altura, aunque se pueden mantener como contenido contextual a demanda.

## Solución incorporada
- `ExecutiveDecisionBoard.jsx`: una sola matriz por dimensiones, con filas seleccionables, barras metodológicas, valor desfavorable global y columnas comparativas de unidades publicables. Usa resultados del backend.
- `ExecutiveDecisionBoard.css`: altura limitada según viewport, barras y etiquetas compactas, tabla con scroll interno y panel lateral fijo.
- Tres indicadores esenciales únicamente: respuestas válidas, máximo desfavorable o dimensiones publicables, y dimensiones de riesgo alto o unidades comparables.
- Filtros coordinados en una sola fila: dimensión, tipo de unidad y unidad. Reinicio coherente.
- Un único panel lateral de diagnóstico con valoración y recomendación de la dimensión seleccionada. No replica recomendaciones globales en unidades.
- Dos modos en el mismo espacio central: diagnóstico y evolución longitudinal, sin duplicar paneles.
- `TelemetryDashboard.jsx`: visualización compacta predeterminada y las herramientas históricas ocultas. El explorador anterior, la calidad de captura y las frecuencias se montan **solo al solicitarse**, evitando consultas innecesarias.
- No se elimina el motor estadístico, la administración de instrumentos, los informes, las licencias ni las rutas técnicas.

## Reglas de integridad
- Solo presentar porcentajes entre 0 y 100 devueltos por el backend.
- No convertir scores genéricos a categorías de riesgo CENSOPAS.
- Validar tripletas favorables/intermedias/desfavorables; aceptar desviación máxima de 1.5 puntos por redondeo, sin recomputarlas.
- Excluir filas `suppressed` y comparaciones no publicables, sin mostrar sus valores.
- No emplear medias de porcentajes para obtener valores de la empresa.
- Clasificaciones y recomendaciones siempre provenientes de funciones del backend.
- Las vistas longitudinales requieren firma de comparabilidad metodológica proporcionada por la API existente.
- Sin acceso a datos de empleados o respuestas individuales desde este tablero.

## Criterios de aceptación
- A 1440 × 900 el tablero ejecutivo debe mostrar cabecera, controles, tres KPI, matriz y hallazgo en una vista, sin scroll vertical del dashboard. Las filas numerosas desplazan **solo** la tabla.
- A 360/390/768 px se permite diseño apilado accesible y scroll vertical natural, nunca recorte de controles ni scroll horizontal de toda la página.
- Los filtros actualizan la matriz y la interpretación; las estadísticas globales deben estar identificadas como tales cuando se comparan unidades.
- Verificar dos organizaciones, al menos dos unidades comparables y un grupo suprimido; no revelar recuentos pequeños.
- Cambio Diagnóstico/Evolución sin nuevo bloque debajo.
- El panel técnico legado no debe cargarse mientras esté oculto.
- El mismo estudio y baremo debe alimentar tablero, vistas avanzadas e informe.
- Ejecutar Vitest, ESLint, Vite build, comprobaciones Python y captura Playwright con datos sintéticos.

## Integración con commit Antigravity local
1. En la máquina del desarrollador, identificar el SHA completo del commit `c815d0c`, rama local, `git status` y diferencias contra `origin/feat/aurora-three-screen-ux-20261021`.
2. Crear respaldo en una rama local y publicar/inspeccionar el commit local sin sobrescribir la rama remota.
3. Comparar especialmente `PremiumBIWorkspace.jsx`, `dashboardModel.js` y `AdaptiveProjectTelemetryPage.jsx` con el nuevo componente aislado.
4. Preservar el ribbon de slicers, matriz o donut que ya aporten valor, pero mantener una sola fuente de filtros y una sola zona central. **No mostrar simultáneamente el nuevo canvas y los paneles de la interfaz local**.
5. Resolver los cambios de composición en `TelemetryDashboard.jsx` y verificar un solo montaje de cada consulta.
6. Ejecutar regresión y E2E, publicar una rama de integración y cerrar esta rama solo tras confirmar equivalencia.

## Pendientes explícitos
- Filtros multidimensionales combinados (sexo + turno + área) necesitan backend de agregados autorizado y controles antiinferencia; no están implementados aquí.
- Aprobación final de layout depende de capturas y pruebas visuales locales sobre la versión con commit `c815d0c`.
- Este PR no fusiona `main`, no lanza servicios locales y no sustituye revisión legal/metodológica.
