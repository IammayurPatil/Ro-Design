// Display-only unit conversions. Factors come from the backend config (/api/config/*).
import type { FlowUnit, InputUnit, IonConstants, IonKey, PressureUnit, UnitConstants, UnitSet } from '../types'

export function unitsFor(u: UnitConstants, set: UnitSet) {
  return u.unitSets[set] ?? u.unitSets.gpm_psi
}

export function flowToDisplay(u: UnitConstants, m3h: number | null | undefined, unit: FlowUnit): number | null {
  if (m3h === null || m3h === undefined) return null
  switch (unit) {
    case 'gpm': return m3h / u.gpmToM3h
    case 'gpd': return (m3h / u.gpmToM3h) * u.gpmToGpd
    case 'm3/d': return m3h * u.m3hToM3d
    default: return m3h
  }
}

export function flowFromDisplay(u: UnitConstants, v: number, unit: FlowUnit): number {
  switch (unit) {
    case 'gpm': return v * u.gpmToM3h
    case 'gpd': return (v / u.gpmToGpd) * u.gpmToM3h
    case 'm3/d': return v / u.m3hToM3d
    default: return v
  }
}

export function pressureToDisplay(u: UnitConstants, bar: number | null | undefined, unit: PressureUnit): number | null {
  if (bar === null || bar === undefined) return null
  return unit === 'psi' ? bar * u.barToPsi : bar
}

export function pressureFromDisplay(u: UnitConstants, v: number, unit: PressureUnit): number {
  return unit === 'psi' ? v / u.barToPsi : v
}

export const FLOW_LABEL: Record<FlowUnit, string> = { gpd: 'gpd', gpm: 'gpm', 'm3/h': 'm³/h', 'm3/d': 'm³/d' }

/** Convert a value typed in the selected input unit to mg/L (rounded like Vontron). */
export function toMgL(c: IonConstants, ion: IonKey, value: number, unit: InputUnit): number {
  const k = c.ions[ion]
  let mg = value
  if (unit === 'ppmCaCO3' && k.caco3Factor) mg = value / k.caco3Factor
  if (unit === 'meq/L' && k.eqWt) mg = value * k.eqWt
  if (c.rounding.roundMgLTo2Decimals) {
    const f = 10 ** c.rounding.mgLDecimals
    mg = Math.round(mg * f + 1e-9) / f
  }
  return mg
}

/** Display a stored mg/L value in another input unit (null when not applicable, e.g. B / SiO2). */
export function fromMgL(c: IonConstants, ion: IonKey, mgL: number, unit: InputUnit): number | null {
  const k = c.ions[ion]
  if (unit === 'mg/L') return mgL
  if (unit === 'ppmCaCO3') return k.caco3Factor ? mgL * k.caco3Factor : null
  return k.eqWt ? mgL / k.eqWt : null
}
