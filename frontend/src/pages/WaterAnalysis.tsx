import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { IonGrid } from '../components/IonGrid'
import { MessagesPanel } from '../components/MessagesPanel'
import { Button, Card, Checkbox, Field, NumberInput, Radio, Select, TextInput } from '../components/ui'
import { useProjectStore } from '../store/projectStore'
import type { InputUnit, IonKey, Message } from '../types'
import { fmt } from '../utils/format'

export default function WaterAnalysis() {
  const { project, constants, setWater, setIon, setProjectInfo, setWaterResult } = useProjectStore()
  const water = project.water
  const analysis = project.results.water
  const [apiError, setApiError] = useState<string | null>(null)
  const [balancing, setBalancing] = useState(false)

  // Recalculate (debounced) whenever the water changes. All maths runs in the backend.
  const waterKey = JSON.stringify(water)
  useEffect(() => {
    const t = setTimeout(() => {
      api.analyzeWater(water)
        .then((r) => { setWaterResult(r); setApiError(null) })
        .catch((e: Error) => setApiError(e.message))
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waterKey])

  const order = constants!.ions.order
  const cations = useMemo(() => order.filter((k) => constants!.ions.ions[k].group === 'cation'), [order, constants])
  const others = useMemo(() => order.filter((k) => constants!.ions.ions[k].group !== 'cation'), [order, constants])
  const locked = !water.specifyIndividualSolutes
  // Individual mode: show what the user entered (no flicker while the analysis refreshes).
  // TDS-only mode: show the Na / Cl split computed by the backend.
  const shownIons = (locked ? analysis?.ionsMgL ?? water.ions : water.ions) as Record<IonKey, number>
  const v = constants!.ions.validation

  const autoBalance = async () => {
    setBalancing(true)
    try {
      const r = await api.autoBalance(water)
      setWater(r.water)
      setWaterResult(r.analysis)
      setApiError(null)
    } catch (e) {
      setApiError((e as Error).message)
    } finally {
      setBalancing(false)
    }
  }

  const messages: Message[] = [
    ...(apiError ? [{ level: 'error' as const, text: apiError }] : []),
    ...(analysis?.messages ?? []),
  ]

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-4">
        <Card title="Project">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Project name"><TextInput value={project.project.name} onChange={(e) => setProjectInfo({ name: e.target.value })} /></Field>
            <Field label="Date"><TextInput type="date" value={project.project.date} onChange={(e) => setProjectInfo({ date: e.target.value })} /></Field>
            <Field label="Designed by"><TextInput value={project.project.designedBy} onChange={(e) => setProjectInfo({ designedBy: e.target.value })} /></Field>
            <Field label="Company"><TextInput value={project.project.company} onChange={(e) => setProjectInfo({ company: e.target.value })} /></Field>
          </div>
        </Card>

        <Card title="Feed water">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Water type">
              <Select value={water.waterType} onChange={(waterType) => setWater({ waterType })}
                options={constants!.waterTypes.map((t) => ({ value: t.name, label: t.name }))} />
            </Field>
            <Field label={`Temperature (°C, ${v.temperatureC.min}–${v.temperatureC.max})`}>
              <NumberInput value={water.temperatureC} min={v.temperatureC.min} max={v.temperatureC.max} dp={1}
                onCommit={(temperatureC) => setWater({ temperatureC })} ariaLabel="Temperature" />
            </Field>
            <Field label={`pH (${v.pH.min}–${v.pH.max})`}>
              <NumberInput value={water.pH} min={v.pH.min} max={v.pH.max} onCommit={(pH) => setWater({ pH })} ariaLabel="pH" />
            </Field>
            <Field label="TDS (mg/L)" hint={locked ? 'Split into Na and Cl.' : 'Calculated from the ions.'}>
              <NumberInput
                ariaLabel="TDS"
                value={locked ? water.tdsInput : analysis?.tds ?? null}
                readOnly={!locked}
                min={0}
                onCommit={(tdsInput) => setWater({ tdsInput: Math.max(tdsInput, 0) })}
              />
            </Field>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-x-8 gap-y-3">
            <Checkbox label="Specify individual solutes" checked={water.specifyIndividualSolutes}
              onChange={(on) => {
                if (on) {
                  // keep the Na / Cl split as the starting point for individual entry
                  setWater({ specifyIndividualSolutes: true, ...(analysis ? { ions: { ...analysis.ionsMgL } } : {}) })
                } else {
                  setWater({ specifyIndividualSolutes: false, tdsInput: water.tdsInput ?? Math.round((analysis?.tds ?? 0) * 100) / 100 })
                }
              }} />
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted">Enter ions in:</span>
              <Radio<InputUnit> name="inputUnit" value={water.inputUnit} onChange={(inputUnit) => setWater({ inputUnit })}
                options={[{ value: 'mg/L', label: 'mg/L' }, { value: 'ppmCaCO3', label: 'ppm CaCO₃' }, { value: 'meq/L', label: 'meq/L' }]} />
            </div>
          </div>
        </Card>

        <Card title="Ions" actions={<Button onClick={autoBalance} disabled={balancing || !analysis || Math.abs(analysis.balance) < 0.05}>{balancing ? 'Balancing…' : 'Auto Balance'}</Button>}>
          <div className="grid gap-6 xl:grid-cols-2">
            <IonGrid title="Cations" ions={cations} mgL={shownIons} analysis={analysis} constants={constants!.ions}
              inputUnit={water.inputUnit} locked={locked} onChange={setIon} />
            <IonGrid title="Anions / neutral" ions={others} mgL={shownIons} analysis={analysis} constants={constants!.ions}
              inputUnit={water.inputUnit} locked={locked} onChange={setIon} />
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <Card title="Summary">
          <dl className="grid grid-cols-2 gap-y-2 text-sm tabular">
            <dt className="text-muted">TDS (mg/L)</dt><dd className="text-right font-semibold">{fmt(analysis?.tds, 2, '—')}</dd>
            <dt className="text-muted">Cations (meq/L)</dt><dd className="text-right">{fmt(analysis?.cations, 1, '—')}</dd>
            <dt className="text-muted">Anions (meq/L)</dt><dd className="text-right">{fmt(analysis?.anions, 1, '—')}</dd>
            <dt className="text-muted">Balance (meq/L)</dt>
            <dd className={`text-right ${analysis?.imbalance ? 'font-semibold text-danger' : ''}`}>{fmt(analysis?.balance, 1, '—')}</dd>
          </dl>
          <p className="mt-3 text-xs text-muted">Boron is counted as boric acid in the TDS.</p>
        </Card>
        <MessagesPanel messages={messages} />
      </div>
    </div>
  )
}
