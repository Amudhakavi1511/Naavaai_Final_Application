import type { Bootstrap } from './types'

/**
 * Port id to display name, populated once from the reference data.
 *
 * The alternative was prop-drilling the whole reference payload into every
 * component that renders a port id — the recommendation panel, the evidence
 * rows, the register. A registry filled before the first render of any of them
 * (App gates rendering on bootstrap) keeps those components reading the way
 * they did when the names were hardcoded, without the hardcoding.
 */
let portNames: Record<string, string> = {}
let commodityNames: Record<string, string> = {}

export function registerReference(bootstrap: Bootstrap): void {
  portNames = {}
  for (const country of bootstrap.origins) {
    for (const port of country.ports) portNames[port.port_id] = port.name
  }
  for (const port of bootstrap.discharge_ports) portNames[port.port_id] = port.name

  commodityNames = {}
  for (const c of bootstrap.commodities) commodityNames[c.id] = c.label
}

/** Falls back to the id with its country prefix stripped, so an unregistered
 *  port (a vessel's open position, say) still reads as a place. */
export function portLabel(id: string): string {
  return portNames[id] ?? id.replace(/^[A-Z]{2}-/, '')
}

export function commodityLabel(id: string): string {
  return commodityNames[id] ?? id.replaceAll('_', ' ')
}
