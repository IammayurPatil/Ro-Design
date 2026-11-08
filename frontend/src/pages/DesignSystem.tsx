import { useCallback, useState } from 'react'
import { api } from '../api/client'
import { ConfigDiagram } from '../components/ConfigDiagram'
import { MessagesPanel } from '../components/MessagesPanel'
import { Badge, Button, Card, Checkbox, Field, NumberInput, Select } from '../components/ui'
import { useAction } from '../hooks'
import { isStale, useProjectStore } from '../store/projectStore'
import type { Message, UnitSet } from '../types'
import { fmt } from '../utils/format'
import { FLOW_LABEL, flowFromDisplay, flowToDisplay, pressureFromDisplay, pressureToDisplay, unitsFor } from '../utils/units'

const UNIT_SETS: { value: UnitSet; label: string }[] = [
  { value: 'gpd_psi', label: 'gpd / psi' },
  { value: 'gpm_psi', label: 'gpm / psi' },
  { value: 'm3h_bar', label: 'm³/h / bar' },
  { value: 'm3d_bar', label: 'm³/d / bar' },
]

function Calculated({ value }: { value: string }) {
  return <div className="rounded-md border border-border bg-surface px-2 py-1 text-right text-sm tabular">{value}</div>
}

export default function DesignSystem() {
  const { project, signatures, constants, setDesign, setPassCount, setStageCount, updatePass, updateStage, setDesignResult } = useProjectStore()
  const d = project.design
  const U = constants!.units
  const { flow: fu, pressure: pu } = unitsFor(U, d.unitSet)
  const result = project.results.design
  const stale = result && isStale(project, signatures, 'design')
  const [passIdx, setPassIdx] = useState(0)
  const [stageIdx, setStageIdx] = useState(0)
  const pi = Math.min(passIdx, d.passes.length - 1)
  const pass = d.passes[pi]
  const si = Math.min(stageIdx, pass.stages.length - 1)
  const stage = pass.stages[si]
  const stageRes = result?.passes?.[pi]?.stages?.[si]
  const passRes = result?.passes?.[pi]

  const calc = useCallback(async () => {
    setDesignResult(await api.calculateDesign(useProjectStore.getState().project))
  }, [setDesignResult])
  const { run, busy, error } = useAction(calc)

  const flow = (m3h: number | null | undefined, dp = 2) => fmt(flowToDisplay(U, m3h, fu), dp, '—')
  const pres = (bar: number | null | undefined) => fmt(pressureToDisplay(U, bar, pu), 2, '—')
  const totalElements = d.passes.reduce((a, p) => a + p.stages.reduce((b, s) => b + s.vessels * s.elementsPerVessel, 0), 0)
  const sys = result?.system
  const elementOptions = constants!.elements.map((e) => ({ value: e.model, label: e.model }))
  const messages: Message[] = [...(error ? [{ level: 'error' as const, text: error }] : []), ...(result?.messages ?? [])]
  const flowDp = fu === 'gpd' || fu === 'm3/d' ? 1 : 3

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-4">
        <Card title="System" actions={stale ? <Badge tone="danger">Out of date</Badge> : undefined}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Unit set">
              <Select value={d.unitSet} options={UNIT_SETS} onChange={(unitSet) => setDesign({ unitSet })} />
            </Field>
            <Field label="Recovery (%)">
              <NumberInput value={d.recoveryPct} min={1} max={99} dp={1} onCommit={(recoveryPct) => setDesign({ recoveryPct })} ariaLabel="Recovery" />
            </Field>
            <Field label={`Permeate flow (${FLOW_LABEL[fu]})`}>
              <NumberInput value={flowToDisplay(U, d.permeateFlow, fu)} dp={flowDp} min={0}
                onCommit={(v) => setDesign({ permeateFlow: flowFromDisplay(U, v, fu) })} ariaLabel="Permeate flow" />
            </Field>
            <Field label={`Feed flow (${FLOW_LABEL[fu]})`}><Calculated value={flow(sys?.feedFlow)} /></Field>
            <Field label="System flux (gfd / LMH)"><Calculated value={sys?.fluxGfd != null ? `${fmt(sys.fluxGfd, 1)} / ${fmt(sys.fluxLmh, 1)}` : '—'} /></Field>
            <Field label="Feed temp (°C)">
              <NumberInput value={d.feedTempC} min={1} max={45} dp={1} onCommit={(feedTempC) => setDesign({ feedTempC })} ariaLabel="Feed temperature" />
            </Field>
            <Field label="Fouling factor (0.5–1.0)">
              <NumberInput value={d.foulingFactor} min={0.5} max={1} onCommit={(foulingFactor) => setDesign({ foulingFactor })} ariaLabel="Fouling factor" />
            </Field>
            <Field label={`Feed pressure (${pu})`}><Calculated value={pres(passRes?.feedPressure ?? sys?.feedPressure)} /></Field>
          </div>
        </Card>

        <Card title="Passes and stages">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Number of passes">
              <Select value={String(d.passes.length)} options={[{ value: '1', label: '1' }, { value: '2', label: '2' }]}
                onChange={(v) => { setPassCount(Number(v)); setPassIdx(0) }} />
            </Field>
            {d.passes.length > 1 && (
              <Field label="Pass">
                <Select value={String(pi)} options={d.passes.map((_, i) => ({ value: String(i), label: `Pass ${i + 1}` }))}
                  onChange={(v) => { setPassIdx(Number(v)); setStageIdx(0) }} />
              </Field>
            )}
            <Field label="Stages in this pass">
              <Select value={String(pass.stages.length)} options={['1', '2', '3'].map((v) => ({ value: v, label: v }))}
                onChange={(v) => { setStageCount(pi, Number(v)); setStageIdx(0) }} />
            </Field>
            <Field label="Total elements"><Calculated value={String(totalElements)} /></Field>
          </div>
          <div className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
            <Checkbox label="Use the same element in the pass" checked={pass.sameElementInPass} onChange={(sameElementInPass) => updatePass(pi, { sameElementInPass })} />
            <Checkbox label="Same back pressure for all stages" checked={pass.sameBackPressure} onChange={(sameBackPressure) => updatePass(pi, { sameBackPressure })} />
          </div>

          <div role="tablist" className="mt-4 flex gap-1 border-b border-border">
            {pass.stages.map((_, i) => (
              <button key={i} role="tab" aria-selected={i === si} onClick={() => setStageIdx(i)}
                className={`-mb-px rounded-t-md border px-3 py-1.5 text-sm ${i === si ? 'border-border border-b-panel bg-panel font-semibold' : 'border-transparent text-muted hover:text-ink'}`}>
                Stage {i + 1}
              </button>
            ))}
          </div>
          <div className="grid gap-3 pt-3 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Pressure vessels">
              <NumberInput value={stage.vessels} dp={0} min={1} onCommit={(v) => updateStage(pi, si, { vessels: Math.max(1, Math.round(v)) })} ariaLabel="Pressure vessels" />
            </Field>
            <Field label="Elements per vessel (1–8)">
              <NumberInput value={stage.elementsPerVessel} dp={0} min={1} max={8}
                onCommit={(v) => updateStage(pi, si, { elementsPerVessel: Math.min(8, Math.max(1, Math.round(v))) })} ariaLabel="Elements per vessel" />
            </Field>
            <Field label="Select product" hint={pass.sameElementInPass && si > 0 ? 'Same as stage 1.' : undefined}>
              <Select value={pass.sameElementInPass ? pass.stages[0].elementModel : stage.elementModel} options={elementOptions}
                disabled={pass.sameElementInPass && si > 0}
                onChange={(elementModel) => (pass.sameElementInPass ? pass.stages.forEach((_, j) => updateStage(pi, j, { elementModel })) : updateStage(pi, si, { elementModel }))} />
            </Field>
            <Field label={`Back pressure (${pu})`} hint={pass.sameBackPressure && si > 0 ? 'Same as stage 1.' : undefined}>
              <NumberInput value={pressureToDisplay(U, pass.sameBackPressure ? pass.stages[0].backPressure : stage.backPressure, pu)} min={0}
                disabled={pass.sameBackPressure && si > 0}
                onCommit={(v) => updateStage(pi, si, { backPressure: pressureFromDisplay(U, Math.max(v, 0), pu) })} ariaLabel="Back pressure" />
            </Field>
            <Field label={`Booster pressure (${pu})`}><Calculated value={pres(stageRes?.boosterPressure)} /></Field>
            <Field label={`Stage feed pressure (${pu})`}><Calculated value={pres(stageRes?.feedPressure)} /></Field>
          </div>
        </Card>

        <Card title="Options">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Checkbox label="Pump efficiency" checked={d.pumpEfficiencyEnabled} onChange={(pumpEfficiencyEnabled) => setDesign({ pumpEfficiencyEnabled })} />
              <NumberInput value={d.pumpEfficiencyPct} dp={1} min={1} max={100} disabled={!d.pumpEfficiencyEnabled}
                onCommit={(pumpEfficiencyPct) => setDesign({ pumpEfficiencyPct })} ariaLabel="Pump efficiency %" />
            </div>
            <div className="space-y-2">
              <Checkbox label="Intake on both ends" checked={d.intakeBothEnds} onChange={(intakeBothEnds) => setDesign({ intakeBothEnds })} />
              <NumberInput value={d.frontEndPct} dp={1} min={0} max={100} disabled={!d.intakeBothEnds}
                onCommit={(frontEndPct) => setDesign({ frontEndPct })} ariaLabel="Front-end %" />
              <p className="text-xs text-muted">Front-end %. Not modelled yet.</p>
            </div>
            <div className="space-y-2">
              <Checkbox label="Recirculation" checked={d.recycle.enabled} onChange={(enabled) => setDesign({ recycle: { ...d.recycle, enabled } })} />
              <NumberInput value={flowToDisplay(U, d.recycle.flow, fu)} dp={flowDp} min={0} disabled={!d.recycle.enabled}
                onCommit={(v) => setDesign({ recycle: { ...d.recycle, flow: flowFromDisplay(U, Math.max(v, 0), fu) } })} ariaLabel="Recycle flow" />
              <p className="text-xs text-muted">Recycle flow ({FLOW_LABEL[fu]})</p>
            </div>
          </div>
        </Card>

        <Card title="System configuration">
          <ConfigDiagram design={d} />
          <div className="mt-4 flex items-center gap-3">
            <Button onClick={() => run()} disabled={busy}>{busy ? 'Calculating…' : 'Calculation'}</Button>
            {stale && <span className="text-sm text-danger">Inputs changed since the last calculation.</span>}
          </div>
        </Card>

        {result && <DesignResults />}
      </div>
      <MessagesPanel messages={messages} />
    </div>
  )
}

function DesignResults() {
  const { project, constants } = useProjectStore()
  const U = constants!.units
  const { flow: fu, pressure: pu } = unitsFor(U, project.design.unitSet)
  const r = project.results.design!
  const s = r.system
  const f = (v: number | null | undefined, dp = 2) => fmt(flowToDisplay(U, v, fu), dp, '—')
  const p = (v: number | null | undefined) => fmt(pressureToDisplay(U, v, pu), 2, '—')
  const rows: [string, string][] = [
    [`Feed flow (${FLOW_LABEL[fu]})`, f(s.feedFlow)],
    [`Permeate flow (${FLOW_LABEL[fu]})`, f(s.permeateFlow)],
    [`Concentrate flow (${FLOW_LABEL[fu]})`, f(s.concentrateFlow)],
    ['Recovery (%)', fmt(s.recoveryPct, 2, '—')],
    ['Average flux (gfd)', fmt(s.fluxGfd, 1, '—')],
    [`Feed pressure (${pu})`, p(s.feedPressure)],
    ['Pump power (kW)', fmt(s.pumpKw, 2, '—')],
    ['Specific energy (kWh/m³)', fmt(s.specificEnergy, 3, '—')],
    ['Permeate TDS (mg/L)', fmt(s.permeateTDS, 2, '—')],
    ['Concentrate TDS (mg/L)', fmt(s.concentrateTDS, 2, '—')],
  ]
  return (
    <Card title="Results">
      <dl className="grid grid-cols-1 gap-x-8 gap-y-1.5 text-sm tabular sm:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between border-b border-border py-1"><dt className="text-muted">{k}</dt><dd>{v}</dd></div>
        ))}
      </dl>
      {r.engineOk && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm tabular">
            <thead>
              <tr className="text-muted">
                {['Pass', 'Stage', 'Element', `Feed (${FLOW_LABEL[fu]})`, `Permeate (${FLOW_LABEL[fu]})`, `Feed P (${pu})`, `ΔP (${pu})`, 'Recovery %', 'Flux (gfd)', 'Permeate TDS'].map((h) => (
                  <th key={h} className="px-2 py-1 text-right font-medium first:text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.passes.flatMap((ps) => ps.stages.flatMap((st) => st.elements.map((e) => (
                <tr key={`${ps.pass}-${st.stage}-${e.position}`} className="border-t border-border text-right">
                  <td className="px-2 py-1 text-left">{ps.pass}</td><td className="px-2">{st.stage}</td><td className="px-2">{e.position}</td>
                  <td className="px-2">{f(e.feedFlow)}</td><td className="px-2">{f(e.permeateFlow, 3)}</td>
                  <td className="px-2">{p(e.feedPressure)}</td><td className="px-2">{fmt(pressureToDisplay(U, e.pressureDrop, pu), 3)}</td>
                  <td className="px-2">{fmt(e.recoveryPct, 2)}</td><td className="px-2">{fmt(e.fluxGfd, 2)}</td><td className="px-2">{fmt(e.permeateTDS, 2)}</td>
                </tr>
              ))))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
