import { useCallback } from 'react'
import { api } from '../api/client'
import { MessagesPanel } from '../components/MessagesPanel'
import { ResultTable } from '../components/ResultTable'
import { Badge, Button, Card, Field, NumberInput, Radio, Select } from '../components/ui'
import { useAction } from '../hooks'
import { isStale, useProjectStore } from '../store/projectStore'
import type { Message, ScalingOption } from '../types'
import { fmt } from '../utils/format'

const OPTIONS: { value: ScalingOption; label: string }[] = [
  { value: 'none', label: 'No chemicals added' },
  { value: 'ph_adjust', label: 'User adjusted pH' },
  { value: 'softening', label: 'Ion exchange softening' },
  { value: 'antiscalant', label: 'Dosing Antiscalants' },
]

export default function Scaling() {
  const { project, signatures, setScaling, setScalingResult } = useProjectStore()
  const sc = project.scaling
  const result = project.results.scaling
  const calc = useCallback(async () => {
    const p = useProjectStore.getState().project
    setScalingResult(await api.calculateScaling(p.water, p.scaling))
  }, [setScalingResult])
  const { run, busy, error } = useAction(calc)
  const stale = result && isStale(project, signatures, 'scaling')

  const messages: Message[] = [
    ...(error ? [{ level: 'error' as const, text: error }] : []),
    ...(result?.messages ?? []),
  ]

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-4">
        <Card title="Scaling inputs">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Recovery (%)">
              <NumberInput value={sc.recoveryPct} min={0} max={99} dp={1} onCommit={(recoveryPct) => setScaling({ recoveryPct })} ariaLabel="Recovery" />
            </Field>
            <Field label="Temp (°C)">
              <NumberInput value={sc.temperatureC} min={1} max={45} dp={1} onCommit={(temperatureC) => setScaling({ temperatureC })} ariaLabel="Temperature" />
            </Field>
            <Field label="Feed water">
              <span className="py-1 text-sm tabular">pH {fmt(project.water.pH, 2)} · TDS {fmt(project.results.water?.tds, 2, '—')} mg/L</span>
            </Field>
          </div>
          <div className="mt-4">
            <Radio name="scalingOption" value={sc.option} options={OPTIONS} onChange={(option) => setScaling({ option })} />
          </div>
          {sc.option === 'ph_adjust' && (
            <div className="mt-4 grid gap-3 rounded-md border border-border p-3 sm:grid-cols-3">
              <Field label="Acid">
                <Select value={sc.phAdjust.chemical} onChange={(chemical) => setScaling({ phAdjust: { ...sc.phAdjust, chemical } })}
                  options={[{ value: 'H2SO4', label: 'H₂SO₄ (sulfuric acid)' }, { value: 'HCl', label: 'HCl (hydrochloric acid)' }]} />
              </Field>
              <Field label="Target pH">
                <NumberInput value={sc.phAdjust.targetPH} min={1} max={13} onCommit={(targetPH) => setScaling({ phAdjust: { ...sc.phAdjust, targetPH } })} ariaLabel="Target pH" />
              </Field>
              <Field label="Acid dose">
                <span className="py-1 text-sm tabular">{result?.acidDose ? `${fmt(result.acidDose.mgL, 2)} mg/L` : '—'}</span>
              </Field>
            </div>
          )}
          {sc.option === 'softening' && (
            <div className="mt-4 grid gap-3 rounded-md border border-border p-3 sm:grid-cols-2">
              <Field label="Ca leakage (mg/L)">
                <NumberInput value={sc.softening.caLeakage} min={0} onCommit={(caLeakage) => setScaling({ softening: { ...sc.softening, caLeakage } })} ariaLabel="Ca leakage" />
              </Field>
              <Field label="Mg leakage (mg/L)">
                <NumberInput value={sc.softening.mgLeakage} min={0} onCommit={(mgLeakage) => setScaling({ softening: { ...sc.softening, mgLeakage } })} ariaLabel="Mg leakage" />
              </Field>
            </div>
          )}
          <div className="mt-4 flex items-center gap-3">
            <Button onClick={() => run()} disabled={busy}>{busy ? 'Calculating…' : 'Scale Calculation'}</Button>
            {stale && <Badge tone="danger">Out of date</Badge>}
            {result && <span className="text-sm text-muted tabular">Concentration factor {fmt(result.cf, 4)}</span>}
          </div>
        </Card>

        <Card title="Results">
          {result ? <ResultTable result={result} /> : <p className="text-sm text-muted">Press “Scale Calculation” to see the results.</p>}
        </Card>
      </div>
      <MessagesPanel messages={messages} />
    </div>
  )
}
