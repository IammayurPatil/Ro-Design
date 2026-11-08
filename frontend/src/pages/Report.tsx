import { useState } from 'react'
import { api } from '../api/client'
import { ElementProfileCharts, IndexChart, IonCompositionChart, SaturationChart } from '../components/charts'
import { MessagesPanel } from '../components/MessagesPanel'
import { ResultTable } from '../components/ResultTable'
import { Badge, Button } from '../components/ui'
import { recalculateAll, useAction } from '../hooks'
import { isStale, useProjectStore } from '../store/projectStore'
import { fileName, fmt, saveBlob } from '../utils/format'
import { FLOW_LABEL, flowToDisplay, pressureToDisplay, unitsFor } from '../utils/units'

const OPTION_LABEL = { none: 'No chemicals added', ph_adjust: 'User adjusted pH', softening: 'Ion exchange softening', antiscalant: 'Dosing Antiscalants' }

export function downloadProjectJson() {
  const { project } = useProjectStore.getState()
  // results are a cache; they are recalculated on load
  const blob = new Blob([JSON.stringify({ ...project, results: {} }, null, 2)], { type: 'application/json' })
  saveBlob(blob, fileName(project.project.name, project.project.date, 'json'))
}

export default function Report() {
  const { project, signatures, constants } = useProjectStore()
  const [dlError, setDlError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const recalc = useAction(recalculateAll)
  const U = constants!.units
  const { flow: fu, pressure: pu } = unitsFor(U, project.design.unitSet)
  const r = project.results
  const info = project.project
  const stale = (['water', 'scaling', 'design'] as const).some((k) => isStale(project, signatures, k))

  const download = async (kind: 'pdf' | 'xlsx') => {
    setBusy(kind)
    setDlError(null)
    try {
      const blob = kind === 'pdf' ? await api.reportPdf(project) : await api.reportXlsx(project)
      saveBlob(blob, fileName(info.name, info.date, kind))
    } catch (e) {
      setDlError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => download('pdf')} disabled={!!busy}>{busy === 'pdf' ? 'Preparing…' : 'Download PDF'}</Button>
        <Button onClick={() => download('xlsx')} disabled={!!busy}>{busy === 'xlsx' ? 'Preparing…' : 'Download Excel'}</Button>
        <Button variant="secondary" onClick={downloadProjectJson}>Download project JSON</Button>
        {stale && (
          <>
            <Badge tone="danger">Preview out of date</Badge>
            <Button variant="secondary" onClick={() => recalc.run()} disabled={recalc.busy}>Recalculate all</Button>
          </>
        )}
        <span className="text-xs text-muted">The PDF and Excel files are always calculated fresh from the current inputs.</span>
      </div>
      {(dlError || recalc.error) && <MessagesPanel messages={[{ level: 'error', text: (dlError || recalc.error)! }]} />}

      <article className="mx-auto max-w-5xl space-y-4 rounded-lg border border-border bg-panel p-4 sm:p-8">
        <header className="flex flex-wrap justify-between gap-2 border-b border-border pb-3">
          <div>
            <h1 className="text-xl font-semibold">RO System Design Report</h1>
            <p className="text-sm text-muted">{info.company}</p>
          </div>
          <div className="text-right text-sm">
            <div className="font-medium">{info.name || 'Untitled project'}</div>
            <div className="text-muted">{info.date}</div>
          </div>
        </header>

        <section>
          <h2 className="mb-2 font-semibold">1. Project information</h2>
          <dl className="grid grid-cols-2 gap-1 text-sm sm:grid-cols-4">
            <dt className="text-muted">Designed by</dt><dd>{info.designedBy}</dd>
            <dt className="text-muted">Water type</dt><dd>{project.water.waterType}</dd>
          </dl>
        </section>

        <section>
          <h2 className="mb-2 font-semibold">2. Water analysis</h2>
          {r.water ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[420px] text-sm tabular">
                <thead><tr className="text-muted"><th className="text-left font-medium">Ion</th><th className="text-right font-medium">mg/L</th><th className="text-right font-medium">ppm CaCO₃</th><th className="text-right font-medium">meq/L</th></tr></thead>
                <tbody>
                  {r.water.order.map((ion) => (
                    <tr key={ion} className="border-t border-border">
                      <td>{ion}</td>
                      <td className="text-right">{fmt(r.water!.rows[ion].mgL)}</td>
                      <td className="text-right">{fmt(r.water!.rows[ion].ppmCaCO3, 2, 'n.a')}</td>
                      <td className="text-right">{fmt(r.water!.rows[ion].meq, 2, 'n.a')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-sm tabular">
                TDS {fmt(r.water.tds)} mg/L · Cations {fmt(r.water.cations, 1)} · Anions {fmt(r.water.anions, 1)} · Balance {fmt(r.water.balance, 1)} meq/L ·
                Temperature {fmt(project.water.temperatureC, 1)} °C · pH {fmt(project.water.pH)}
              </p>
            </div>
          ) : <p className="text-sm text-muted">Not calculated.</p>}
        </section>

        <section>
          <h2 className="mb-2 font-semibold">3. Scaling</h2>
          {r.scaling ? (
            <>
              <p className="mb-2 text-sm">
                Option: {OPTION_LABEL[r.scaling.option]} · Recovery {fmt(r.scaling.recoveryPct, 1)}% · Temperature {fmt(r.scaling.temperatureC, 1)} °C ·
                CF {fmt(r.scaling.cf, 4)}{r.scaling.acidDose ? ` · Acid dose ${fmt(r.scaling.acidDose.mgL)} mg/L ${r.scaling.acidDose.chemical}` : ''}
              </p>
              <ResultTable result={r.scaling} />
              <ul className="mt-2 space-y-1 text-sm">
                {r.scaling.messages.filter((m) => m.level !== 'info').map((m, i) => <li key={i} className="text-danger">{m.text}</li>)}
              </ul>
            </>
          ) : <p className="text-sm text-muted">Not calculated.</p>}
        </section>

        <section>
          <h2 className="mb-2 font-semibold">4. Design</h2>
          <ul className="mb-2 text-sm">
            {project.design.passes.map((p, pi) => p.stages.map((s, si) => (
              <li key={`${pi}${si}`}>Pass {pi + 1}, stage {si + 1}: {s.vessels} vessel(s) × {s.elementsPerVessel} element(s), {p.sameElementInPass ? p.stages[0].elementModel : s.elementModel}</li>
            )))}
          </ul>
          {r.design ? (
            <>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm tabular sm:grid-cols-4">
                <dt className="text-muted">Feed ({FLOW_LABEL[fu]})</dt><dd>{fmt(flowToDisplay(U, r.design.system.feedFlow, fu), 2, '—')}</dd>
                <dt className="text-muted">Permeate ({FLOW_LABEL[fu]})</dt><dd>{fmt(flowToDisplay(U, r.design.system.permeateFlow, fu), 2, '—')}</dd>
                <dt className="text-muted">Concentrate ({FLOW_LABEL[fu]})</dt><dd>{fmt(flowToDisplay(U, r.design.system.concentrateFlow, fu), 2, '—')}</dd>
                <dt className="text-muted">Recovery (%)</dt><dd>{fmt(r.design.system.recoveryPct, 1, '—')}</dd>
                <dt className="text-muted">Flux (gfd)</dt><dd>{fmt(r.design.system.fluxGfd, 1, '—')}</dd>
                <dt className="text-muted">Feed pressure ({pu})</dt><dd>{fmt(pressureToDisplay(U, r.design.system.feedPressure, pu), 2, '—')}</dd>
                <dt className="text-muted">Permeate TDS</dt><dd>{fmt(r.design.system.permeateTDS, 2, '—')}</dd>
                <dt className="text-muted">Energy (kWh/m³)</dt><dd>{fmt(r.design.system.specificEnergy, 3, '—')}</dd>
              </dl>
              <ul className="mt-2 space-y-1 text-sm">
                {r.design.messages.map((m, i) => <li key={i} className={m.level === 'info' ? 'text-muted' : 'text-danger'}>{m.text}</li>)}
              </ul>
              <p className="mt-1 text-xs text-muted">Per-stage and per-element tables are in the PDF and Excel downloads and on the Design System page.</p>
            </>
          ) : <p className="text-sm text-muted">Not calculated.</p>}
        </section>

        <section>
          <h2 className="mb-2 font-semibold">5. Charts</h2>
          <div className="grid gap-4 lg:grid-cols-2">
            <SaturationChart scaling={r.scaling} />
            <IndexChart scaling={r.scaling} />
            <IonCompositionChart feed={r.water?.ionsMgL ?? null}
              concentrate={r.design?.engineOk ? r.design.system.concentrateIons : r.scaling?.columns.concentrate.ions ?? null}
              permeate={r.design?.engineOk ? r.design.system.permeateIons : null} />
            <ElementProfileCharts design={r.design} units={U} unitSet={project.design.unitSet} />
          </div>
        </section>

        <section>
          <h2 className="mb-2 font-semibold">6. Notes and disclaimer</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            <li>Water Analysis and the core Scaling formulas reproduce Vontron RO Design Software 6.1 (verified by golden tests).</li>
            <li>Provisional (not yet confirmed against Vontron): the design engine (pressures, permeate quality, energy), pH adjustment, softening,
              antiscalant limits, the CaCO₃ (LSI) warning threshold, the general Ksp form, S&DSI above I = 0.13, the SrSO₄ step at TDS 4000 and the design limits per water type.</li>
            <li>Missing element datasheet values are reported as errors, not guessed.</li>
          </ul>
        </section>
      </article>
    </div>
  )
}
