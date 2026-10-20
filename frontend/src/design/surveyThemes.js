/**
 * Registro de skins visuales para el formulario que ven los encuestados
 * (PublicSurveyPage). Se elige y edita en el paso "Formulario" del builder
 * (SurveyThemePicker) y se guarda en `project.metadata.form_theme`:
 *   { style: 'colmena' | 'modernist', colors: { accent?, bg?, text? },
 *     layout: { questionsPerScreen: 'single' | 'all', align: 'center' | 'left' } }
 *
 * La parte estructural de cada skin (radios, grosor de borde, tipografía,
 * mayúsculas en labels) vive en index.css bajo `.survey-shell` /
 * `[data-survey-skin="modernist"]`. Este módulo sólo describe lo que el
 * usuario puede elegir y editar, para que el picker y la página pública
 * lean la misma fuente de verdad.
 */

export const DEFAULT_SURVEY_STYLE = 'colmena';

export const SURVEY_THEME_STYLES = {
  colmena: {
    id: 'colmena',
    label: 'Aurora',
    description: 'Vidrio, azul y ámbar — el estilo por defecto de la app.',
    fontLabel: 'Inter',
    defaultColors: {
      accent: '#F5B21A',
      bg: '#FAFAF8',
      text: '#111111',
    },
  },
  modernist: {
    id: 'modernist',
    label: 'Modernist',
    description: 'Editorial, esquinas rectas y tipografía Archivo — tomado de survey_squeleton.',
    fontLabel: 'Archivo',
    defaultColors: {
      accent: '#EC3013',
      bg: '#F3F2F2',
      text: '#201E1D',
    },
  },
};

export const EDITABLE_SURVEY_COLORS = [
  { key: 'accent', label: 'Color de acento' },
  { key: 'bg', label: 'Fondo' },
  { key: 'text', label: 'Texto' },
];

/**
 * survey_squeleton/Likability Survey.dc.html no pide una pregunta por vez:
 * muestra el bloque completo (Likert Q1-Q5, opción única, múltiple, NPS,
 * ranking) en una sola pantalla larga, sin centrar el contenido — el
 * contenedor (`max-width: 1080px; padding: 0 40px`) no tiene margin:auto,
 * queda pegado al borde izquierdo. `single` es el flujo original de
 * Colmena (una tarjeta centrada, Atrás/Continuar); `all` es ese layout.
 */
export const QUESTIONS_PER_SCREEN_OPTIONS = [
  { id: 'single', label: 'Una pregunta a la vez', description: 'Tarjeta centrada, avanza con Atrás / Continuar.' },
  { id: 'all', label: 'Todas las preguntas en pantalla', description: 'Lista completa en una sola vista, como survey_squeleton.' },
];

export const ALIGN_OPTIONS = [
  { id: 'center', label: 'Centrado' },
  { id: 'left', label: 'A un costado (izquierda)' },
];

export const DEFAULT_LAYOUT = {
  questionsPerScreen: 'single',
  align: 'center',
};

export function getSurveyThemeStyle(styleId) {
  return SURVEY_THEME_STYLES[styleId] || SURVEY_THEME_STYLES[DEFAULT_SURVEY_STYLE];
}

/** Normaliza lo que venga guardado (posiblemente vacío/parcial) a { style, colors, layout } completos. */
export function resolveSurveyTheme(formTheme) {
  const style = getSurveyThemeStyle(formTheme?.style);
  return {
    style: style.id,
    colors: {
      ...style.defaultColors,
      ...(formTheme?.colors || {}),
    },
    layout: {
      questionsPerScreen: formTheme?.layout?.questionsPerScreen === 'all' ? 'all' : DEFAULT_LAYOUT.questionsPerScreen,
      align: formTheme?.layout?.align === 'left' ? 'left' : DEFAULT_LAYOUT.align,
    },
  };
}

/** CSS custom properties a inyectar inline sobre `.survey-shell[data-survey-skin]`. */
export function buildSurveyThemeVars({ colors }) {
  return {
    '--survey-accent': colors.accent,
    '--survey-bg': colors.bg,
    '--survey-text': colors.text,
  };
}
