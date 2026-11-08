import { ElementProfileCharts, IndexChart, IonCompositionChart, SaturationChart } from '../components/charts'
import { MessagesPanel } from '../components/MessagesPanel'
import { Badge, Button, Card } from '../components/ui'
import { recalculateAll, useAction } from '../hooks'
import { isStale, useProjectStore } from '../store/projectStore'
import type { IndexStatus, Message, Project } from '../types'
import { fmt } from '../utils/format'
import { FLOW_LABEL, flowToDisplay, pressureToDisplay, unitsFor } from '../utils/units'

export function allMessages(project: Project): Message[] {
  const r = project.results
  return [
    ...(r.water?.messages ?? []).map((m) => ({ ...m, page: 'Water Analysis' })),
    ...(r.scaling?.messages ?? []).map((m) => ({ ...m, page: 'Scaling' })),
    ...(r.design?.messages ?? []).map((m) => ({ ...m, page: 'Design System' })),
  ]
}

const STATUS_STYLE: Record<IndexStatus['status'], { color: string; icon: string; label: string }> = {
  green: { color: 'var(--status-good)', icon: '✓', label: 'OK' },
  amber: { color: 'var(--status-warning)', icon: '!', label: 'Near limit' },
  red: { color: 'var(--status-critical)', icon: '✕', label: 'Over limit' },
  'n/a': { color: 'var(--muted)', icon: '–', label: 'N/A' },
}

function Kpi({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="rounded-lg border border-border bg-panel p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular">
        {value}{unit && <span className="ml-1 text-xs font-normal text-muted">{unit}</span>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { project, signatures, constants } = useProjectStore()
  const { run, busy, error } = useAction(recalculateAll)
  const U = constants!.units
  const { flow: fu, pressure: pu } = unitsFor(U, project.design.unitSet)
  const r = project.results
  const s = r.design?.system
  const stale = (['water', 'scaling', 'design'] as const).some((k) => isStale(project, signatures, k))
  const flow = (v?: number | null) => fmt(flowToDisplay(U, v, fu), 2, '—')
  const messages = [...(error ? [{ level: 'error' as const, text: error }] : []), ...allMessages(project)]
  const warnings = messages.filter((m) => m.level !== 'info')

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold">{project.project.name || 'Untitled project'}</h1>
        {stale ? <Badge tone="danger">Out of date</Badge> : <Badge>Up to date</Badge>}
        <Button className="ml-auto" onClick={() => run()} disabled={busy}>{busy ? 'Recalculating…' : 'Recalculate all'}</Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Kpi label="Feed flow" value={flow(s?.feedFlow)} unit={FLOW_LABEL[fu]} />
        <Kpi label="Permeate flow" value={flow(s?.permeateFlow)} unit={FLOW_LABEL[fu]} />
        <Kpi label="Concentrate flow" value={flow(s?.concentrateFlow)} unit={FLOW_LABEL[fu]} />
        <Kpi label="Recovery" value={fmt(s?.recoveryPct, 1, '—')} unit="%" />
        <Kpi label="Average flux" value={fmt(s?.fluxGfd, 1, '—')} unit="gfd" />
        <Kpi label="Feed pressure" value={fmt(pressureToDisplay(U, s?.feedPressure, pu), 1, '—')} unit={pu} />
        <Kpi label="Permeate TDS" value={fmt(s?.permeateTDS, 1, '—')} unit="mg/L" />
        <Kpi label="Specific energy" value={fmt(s?.specificEnergy, 3, '—')} unit="kWh/m³" />
        <Kpi label="Feed TDS" value={fmt(r.water?.tds, 1, '—')} unit="mg/L" />
        <Kpi label="Water type" value={project.water.waterType} />
      </div>

      <Card title="Scaling status (concentrate)">
        {r.scaling ? (
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {Object.entries(r.scaling.status).map(([name, st]) => {
              const sty = STATUS_STYLE[st.status]
              return (
                <li key={name} className="flex items-center gap-2 rounded-md border border-border p-2">
                  <span aria-hidden className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white" style={{ background: sty.color }}>{sty.icon}</span>
                  <div className="min-w-0 text-sm">
                    <div className="font-medium">{name}{st.index ? ` (${st.index})` : ''}</div>
                    <div className="text-xs text-muted tabular">
                      {st.value === null ? 'N/A' : st.index ? fmt(st.value, 2) : `${fmt(st.value, 1)} %`} · {sty.label}
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        ) : <p className="text-sm text-muted">Run the scale calculation (or Recalculate all).</p>}
        <p className="mt-2 text-xs text-muted">Green: below 80% of the limit · Amber: 80–100% · Red: over the limit.</p>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <SaturationChart scaling={r.scaling} />
        <IonCompositionChart
          feed={r.water?.ionsMgL ?? null}
          concentrate={r.design?.engineOk ? r.design.system.concentrateIons : r.scaling?.columns.concentrate.ions ?? null}
          permeate={r.design?.engineOk ? r.design.system.permeateIons : null}
        />
        <ElementProfileCharts design={r.design} units={U} unitSet={project.design.unitSet} />
        <IndexChart scaling={r.scaling} />
      </div>

      <MessagesPanel title={`All warnings (${warnings.length})`} messages={warnings} showPage />
    </div>
  )
}
