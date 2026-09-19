export function usd(n: number): string {
  return `$${Math.round(n).toLocaleString('en-US')}`
}

export function pct(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}
