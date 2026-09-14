export function usd(n: number): string {
  return `$${Math.round(n).toLocaleString('en-US')}`
}

export function pct(n: number): string {
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}%`
}

export function riskColor(label: string): string {
  if (label === 'LOW') return 'text-sea'
  if (label === 'HIGH') return 'text-rust'
  return 'text-brass'
}
