# Colmena Frontend

Primera iteración: **login, signup y dashboard**, según lo pedido — no el frontend completo de `../CODEX_HARNESS_COLMENA_FRONTEND.md` (Proyectos, Instrumentos, Surveys, Analítica, etc. quedan para una próxima iteración).

## Lenguaje visual

Se usa el sistema glass/azul/amarillo ya establecido de Colmena (`--colmena-*` en `src/index.css`, copiado de `../colmena_layout_css.md`) como piel visual completa. De `../survey_squeleton/` (design system "Modernist": rojo, radius 0, tipografía Archivo) sólo se tomaron ideas **estructurales** — micro-labels en mayúsculas con tracking (`.colmena-label`), grid limpio en los formularios — nunca sus colores ni esquinas rectas, que chocan con el lenguaje glass de Colmena. Ver decisión completa en el plan de esta sesión.

Colmena corre aquí como app **standalone** con su propio login/signup (no embebida en AppThesis vía SSO, ya que ese repo no existe en este proyecto) — por eso `ColmenaLayout.jsx` reconstruye un shell equivalente al `StudentLayout.jsx` documentado, no lo importa.

## Requisitos

- Node.js 20+ (usar `nvm use` — hay un `.nvmrc`)
- Backend Colmena corriendo (`../backend`, ver su README)

## Setup

```bash
cd frontend
nvm use
npm install
cp .env.example .env   # ajustar VITE_API_BASE_URL si el backend no está en localhost:8000
npm run dev
```

La app queda en `http://localhost:5175`.

## Build

```bash
npm run build
```

## Estructura

```
src/
├── api/            # cliente HTTP centralizado (client.js) + módulos por dominio (auth.js, projects.js)
├── auth/           # AuthContext (token en localStorage) + ProtectedRoute
├── components/ui/  # GlassCard, PrimaryButton, SecondaryButton, FormField, PageHeader, MetricCard, EmptyState
├── layouts/         # ColmenaLayout (topbar + shell)
└── pages/           # LoginPage, SignupPage, DashboardPage
```

## Pendiente (fuera de alcance de esta iteración)

- Resto de páginas del harness (Proyectos, Instrumentos, Surveys, Estudios, Analítica, CENSOPAS, Reportes, Exportaciones).
- TanStack Table para tablas paginadas server-side (§54) — el dashboard usa una tabla simple por ahora.
- Tests (Vitest + React Testing Library, §67).
