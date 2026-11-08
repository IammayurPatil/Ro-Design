import clsx from 'clsx'
import type { ScalingResult } from '../types'
import { fmt } from '../utils/format'

export const SCALING_ROWS: { key: keyof ScalingResult['columns']['feed']; label: string; limit?: boolean }[] = [
  { key: 'pH', label: 'pH' },
  { key: 'TDS', label: 'TDS (mg/L)' },
  { key: 'HCO3', label: 'HCO₃ (mg/L)' },
  { key: 'CO3', label: 'CO₃ (mg/L)' },
  { key: 'CO2', label: 'CO₂ (mg/L)' },
  { key: 'LSI', label: 'LSI' },
  { key: 'SDSI', label: 'Stiff & Davis Stability Index' },
  { key: 'CaSO4', label: 'CaSO₄ Saturation %', limit: true },
  { key: 'BaSO4', label: 'BaSO₄ Saturation %', limit: true },
  { key: 'SrSO4', label: 'SrSO₄ Saturation %', limit: true },
  { key: 'CaF2', label: 'CaF₂ Saturation %', limit: true },
  { key: 'SiO2', label: 'SiO₂ Saturation %', limit: true },
]

/** Scaling result table: rows = indices, columns = Feed | Adjusted Feed | Concentrate. */
export function ResultTable({ result }: { result: ScalingResult }) {
  const cols = [
    { key: 'feed', label: 'Feed' },
    { key: 'adjusted', label: 'Adjusted Feed' },
    { key: 'concentrate', label: 'Concentrate' },
  ] as const
  const flagged = new Set(result.messages.filter((m) => m.level === 'warning').map((m) => m.text.split(' ')[0]))
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-sm tabular">
        <thead>
          <tr className="text-muted">
            <th className="py-1.5 text-left font-medium"></th>
            {cols.map((c) => <th key={c.key} className="px-2 py-1.5 text-right font-medium">{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {SCALING_ROWS.map((r) => {
            const warnKey = r.key === 'LSI' ? 'CaCO3' : r.key
            return (
              <tr key={r.key} className="border-t border-border">
                <th scope="row" className="py-1.5 text-left font-normal">{r.label}</th>
                {cols.map((c) => {
                  const v = result.columns[c.key][r.key] as number | null
                  const bad = c.key === 'concentrate' && flagged.has(warnKey)
                  return (
                    <td key={c.key} className={clsx('px-2 py-1.5 text-right', bad && 'font-semibold text-danger')}>
                      {fmt(v, 2)}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
