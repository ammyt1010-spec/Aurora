# AURORA Professional | Guía de marca v1.0

**Fuente de verdad documental:** `AURORA Professional - Manual de Marca v1.0` (paquete de archivos entregado el 22/10/2026).

## Identidad
Marca: AURORA Professional. Promesa: **Datos complejos, decisiones claras**.
Isotipo: tres ondas de aurora boreal que evocan análisis, progreso y conectividad.
El producto es empresarial y multidisciplinario, no debe etiquetarse exclusivamente como riesgos psicosociales.

## Colores
| Token | HEX | Uso |
|---|---|---|
| Navy | `#0A1F44` | Palabra AURORA, navegación y alto contraste |
| Cyan | `#00D4D8` | Acento de gradiente |
| Violet | `#6366F1` | Acento secundario |
| Emerald | `#10B981` | Estado favorable |
| Canvas | `#F8FAFC` | Fondo tema claro |
| Slate | `#64748B` | Texto secundario |
| Border | `#E2E8F0` | Bordes y separadores |
| Warning | `#F59E0B` | Advertencia |
| Danger | `#EF4444` | Riesgo / error |

Las categorías estadísticas no deben deducirse del color. Un valor no publicable nunca se pinta verde ni se reemplaza por cero.

## Tipografía
Inter para UI; encabezados 28-32 px; secciones 20-24 px; cuerpo 13-16 px; etiquetas 12-14 px; caption 11-12 px.
Mantener contraste y foco visible según criterios WCAG 2.2 AA cuando corresponda.

## Activos
- `frontend/public/brand/aurora-isotipo.svg`
- `frontend/public/brand/aurora-horizontal.svg`
- `frontend/public/brand/favicon.svg`
- `frontend/public/brand/aurora-light-waves.svg`
- `frontend/public/brand/aurora-dark-waves.svg`
- `frontend/src/brand/BrandMark.jsx` (vector JSX coordinado)
- `frontend/src/brand/BrandLogo.jsx` (marca textual)
- `frontend/src/brand/brand-tokens.css`
- `frontend/src/design/aurora-brand.css`
- `backend/app/services/report_docx/theme.py` (paleta de salida DOCX/PDF)

## Aplicación
1. Tema claro por defecto y aurora solo como motivo atmosférico, sin competir con datos.
2. Tres pantallas principales: Inicio, Telemetría, Informe.
3. Un solo logotipo para sidebar, cabecera, favicon, informes y entrega de documentación.
4. Dashboard denso, interactivo, semáforos con etiquetas, segmentos y controles verificables.
5. No decorar con gráficos o métricas ficticias en entornos operativos.
6. Revalidar CI, navegador real y PDF DOCX tras cambios de marca.

## Estado y limitaciones
La implementación tiene prueba automatizada de build/lint, pero las pantallas requieren revisión visual humana en 360, 768 y 1440 px y contraste en estados reales.
La propuesta no acredita registro de marca ni certificación normativa.
