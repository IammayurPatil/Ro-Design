import type { InputUnit, IonConstants, IonKey, WaterResult } from '../types'
import { fmt } from '../utils/format'
import { fromMgL, toMgL } from '../utils/units'
import { NumberInput } from './ui'

const COLS: { unit: InputUnit; label: string; key: 'mgL' | 'ppmCaCO3' | 'meq' }[] = [
  { unit: 'mg/L', label: 'mg/L', key: 'mgL' },
  { unit: 'ppmCaCO3', label: 'ppm CaCO₃', key: 'ppmCaCO3' },
  { unit: 'meq/L', label: 'meq/L', key: 'meq' },
]

const ION_LABEL: Partial<Record<IonKey, string>> = {
  NH4: 'NH₄', CO3: 'CO₃', HCO3: 'HCO₃', NO3: 'NO₃', SO4: 'SO₄', SiO2: 'SiO₂',
}

/**
 * Ion table. Only the column of the selected input unit is editable; B and SiO2 show "n.a"
 * in the other two columns. Values shown come from the backend analysis when available.
 */
export function IonGrid({
  title, ions, mgL, analysis, constants, inputUnit, locked, onChange,
}: {
  title: string
  ions: IonKey[]
  mgL: Record<IonKey, number>
  analysis: WaterResult | null | undefined
  constants: IonConstants
  inputUnit: InputUnit
  locked: boolean
  onChange: (ion: IonKey, mgL: number) => void
}) {
  return (
    <table className="w-full text-sm tabular">
      <thead>
        <tr className="text-left text-muted">
          <th className="py-1 pr-2 font-medium">{title}</th>
          {COLS.map((c) => (
            <th key={c.unit} className="px-1 py-1 text-right font-medium">{c.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {ions.map((ion) => {
          const neutral = constants.ions[ion].eqWt === null
          return (
            <tr key={ion} className="border-t border-border">
              <th scope="row" className="py-1 pr-2 text-left font-medium">{ION_LABEL[ion] ?? ion}</th>
              {COLS.map((c) => {
                const notApplicable = neutral && c.unit !== 'mg/L'
                const editable = c.unit === inputUnit && !locked && !notApplicable
                const row = analysis?.rows?.[ion]
                const value = row ? row[c.key] : fromMgL(constants, ion, mgL[ion] ?? 0, c.unit)
                return (
                  <td key={c.unit} className="px-1 py-0.5 text-right">
                    {notApplicable ? (
                      <span className="text-muted">n.a</span>
                    ) : editable ? (
                      <NumberInput
                        ariaLabel={`${ion} ${c.label}`}
                        className="w-24"
                        value={fromMgL(constants, ion, mgL[ion] ?? 0, c.unit)}
                        min={0}
                        onCommit={(v) => onChange(ion, toMgL(constants, ion, Math.max(v, 0), c.unit))}
                      />
                    ) : (
                      <span className="inline-block w-24 px-2">{fmt(value, 2)}</span>
                    )}
                  </td>
                )
              })}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
