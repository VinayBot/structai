/** Formats a millisecond duration with one decimal place, e.g. "123.4ms". */
export function formatMs(ms: number): string {
  return `${ms.toFixed(1)}ms`
}
