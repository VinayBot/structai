export type EvalThemeMode = 'light' | 'dark'

export interface EvalPalette {
  primary: string
  secondary: string
  tertiary: string
  success: string
  warning: string
  danger: string
  bg: string
  surface: string
  surfaceRaised: string
  border: string
  text: string
  textDim: string
}

/** Literal hex values for direct use as Recharts stroke/fill props — SVG chart
 * libs are safer fed resolved colors than CSS vars read at render time. Dark
 * values alias the app's existing --color-* tokens (see index.css); light
 * values are page-scoped to the Evaluation tab only. */
export const EVAL_PALETTE: Record<EvalThemeMode, EvalPalette> = {
  light: {
    primary: '#4f6ee6',
    secondary: '#6cc4b8',
    tertiary: '#f0c050',
    success: '#1f9d6a',
    warning: '#b9770e',
    danger: '#d6425a',
    bg: '#ffffff',
    surface: '#ffffff',
    surfaceRaised: '#f5f6fa',
    border: '#e2e5ec',
    text: '#1a1d29',
    textDim: '#6b7280',
  },
  dark: {
    primary: '#7c5cff',
    secondary: '#a855f7',
    tertiary: '#e4b94c',
    success: '#35d08f',
    warning: '#ffb454',
    danger: '#ff5c6c',
    bg: '#0b0b10',
    surface: '#1c1c27',
    surfaceRaised: '#15151d',
    border: '#2a2a38',
    text: '#e4e4ea',
    textDim: '#9494a3',
  },
}

export const EVAL_THEME_STORAGE_KEY = 'eval:theme'

export function loadEvalTheme(): EvalThemeMode {
  try {
    const raw = localStorage.getItem(EVAL_THEME_STORAGE_KEY)
    return raw === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

export function saveEvalTheme(mode: EvalThemeMode): void {
  try {
    localStorage.setItem(EVAL_THEME_STORAGE_KEY, mode)
  } catch {
    // best-effort persistence only
  }
}
