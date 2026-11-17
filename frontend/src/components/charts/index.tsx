// Charts (Recharts). Categorical slots in fixed order: Feed = series-1, Concentrate = series-2, Permeate = series-3.
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { DesignResult, IonKey, ScalingResult, UnitConstants, UnitSet } from '../../types'
import { fmt } from '../../utils/format'
import { pressureToDisplay, unitsFor } from '../../utils/units'

const AXIS = { stroke: 'var(--muted)', fontSize: 11, tickLine: false }
const GRID = <CartesianGrid stroke="var(--grid)" vertical={false} />
const TOOLTIP_STYLE = {
  contentStyle: { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12, color: 'var(--ink)' },
  labelStyle: { color: 'var(--ink)', fontWeight: 600 },
  cursor: { fill: 'var(--grid)', opacity: 0.5 },
}

function Frame({ title, children, note }: { title: string; children: React.ReactNode; note?: string }) {
  return (
    <figure className="rounded-lg border border-border bg-panel p-3">
      <figcaption className="mb-2 text-sm font-semibold">{title}</figcaption>
      <div className="h-64 w-full">{children}</div>
      {note && <p className="mt-1 text-xs text-muted">{note}</p>}
    </figure>
  )
}

export function Empty({ title, text }: { title: string; text: string }) {
  return (
    <figure className="rounded-lg border border-dashed border-border bg-panel p-3">
      <figcaption className="mb-2 text-sm font-semibold">{title}</figcaption>
      <div className="flex h-64 items-center justify-center text-center text-sm text-muted">{text}</div>
    </figure>
  )
}

const SALTS = ['CaSO4', 'BaSO4', 'SrSO4', 'CaF2', 'SiO2'] as const

export function SaturationChart({ scaling }: { scaling: ScalingResult | null | undefined }) {
  if (!scaling) return <Empty title="Saturation %" text="Run the scale calculation to see this chart." />
  const data = SALTS.map((s) => ({
    name: s, Feed: scaling.columns.feed[s] ?? 0, Concentrate: scaling.columns.concentrate[s] ?? 0,
  }))
  return (
    <Frame title="Saturation %, Feed vs Concentrate" note="Dashed line: 100% saturation limit.">
      <ResponsiveContainer>
        <BarChart data={data} barGap={2} margin={{ top: 8, right: 40, left: 0, bottom: 0 }}>
          {GRID}
          <XAxis dataKey="name" {...AXIS} />
          <YAxis {...AXIS} width={48} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(v: number) => `${fmt(v, 2)} %`} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={100} stroke="var(--danger)" strokeDasharray="4 3" label={{ value: '100%', position: 'right', fill: 'var(--danger)', fontSize: 10 }} />
          <Bar dataKey="Feed" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={22} />
          <Bar dataKey="Concentrate" fill="var(--series-2)" radius={[4, 4, 0, 0]} maxBarSize={22} />
        </BarChart>
      </ResponsiveContainer>
    </Frame>
  )
}

export function IndexChart({ scaling }: { scaling: ScalingResult | null | undefined }) {
  if (!scaling) return <Empty title="LSI and S&DSI" text="Run the scale calculation to see this chart." />
  const c = scaling.columns
  const data = [
    { name: 'LSI', Feed: c.feed.LSI, Concentrate: c.concentrate.LSI },
    { name: 'S&DSI', Feed: c.feed.SDSI, Concentrate: c.concentrate.SDSI },
  ]
  const na = data.every((d) => d.Feed === null)
  if (na) return <Empty title="LSI and S&DSI" text="N/A: no calcium or bicarbonate in the water (no CaCO₃ scaling risk)." />
  return (
    <Frame title="LSI and S&DSI, Feed vs Concentrate" note="Above 0 the water tends to form CaCO₃ scale.">
      <ResponsiveContainer>
        <BarChart data={data} barGap={2} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          {GRID}
          <XAxis dataKey="name" {...AXIS} />
          <YAxis {...AXIS} width={48} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(v: number) => fmt(v, 2)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={0} stroke="var(--muted)" />
          <Bar dataKey="Feed" fill="var(--series-1)" radius={[4, 4, 4, 4]} maxBarSize={36} />
          <Bar dataKey="Concentrate" fill="var(--series-2)" radius={[4, 4, 4, 4]} maxBarSize={36} />
        </BarChart>
      </ResponsiveContainer>
    </Frame>
  )
}

// Ion composition: 7 named ions + "Other" = 8 categorical slots (never more).
const COMP_GROUPS: { key: string; ions: IonKey[]; color: string }[] = [
  { key: 'Na', ions: ['Na'], color: 'var(--series-1)' },
  { key: 'Cl', ions: ['Cl'], color: 'var(--series-2)' },
  { key: 'Ca', ions: ['Ca'], color: 'var(--series-3)' },
  { key: 'Mg', ions: ['Mg'], color: 'var(--series-4)' },
  { key: 'HCO3', ions: ['HCO3'], color: 'var(--series-5)' },
  { key: 'SO4', ions: ['SO4'], color: 'var(--series-6)' },
  { key: 'SiO2', ions: ['SiO2'], color: 'var(--series-7)' },
  { key: 'Other', ions: ['K', 'Ba', 'Sr', 'NH4', 'B', 'CO3', 'F', 'NO3'], color: 'var(--series-8)' },
]

export function IonCompositionChart({ feed, concentrate, permeate }: {
  feed?: Record<IonKey, number> | null
  concentrate?: Record<IonKey, number> | null
  permeate?: Record<IonKey, number> | null
}) {
  const streams = [
    ['Feed', feed], ['Concentrate', concentrate], ['Permeate', permeate],
  ] as const
  const data = streams.filter(([, ions]) => ions).map(([name, ions]) => {
    const row: Record<string, number | string> = { name }
    for (const g of COMP_GROUPS) row[g.key] = g.ions.reduce((a, k) => a + (ions![k] ?? 0), 0)
    return row
  })
  if (data.length === 0) return <Empty title="Ion composition" text="Enter a water analysis to see this chart." />
  return (
    <Frame title="Ion composition (mg/L)" note={permeate ? undefined : 'Permeate appears after a successful design calculation.'}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          {GRID}
          <XAxis dataKey="name" {...AXIS} />
          <YAxis {...AXIS} width={56} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(v: number) => `${fmt(v, 2)} mg/L`} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {COMP_GROUPS.map((g, i) => (
            <Bar key={g.key} dataKey={g.key} stackId="a" fill={g.color} stroke="var(--panel)" strokeWidth={1}
              maxBarSize={56} radius={i === COMP_GROUPS.length - 1 ? [4, 4, 0, 0] : undefined} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </Frame>
  )
}

/** Per-element flux and pressure: two separate panels (never a dual axis). */
export function ElementProfileCharts({ design, units, unitSet }: { design: DesignResult | null | undefined; units: UnitConstants; unitSet: UnitSet }) {
  const title = 'Per-element flux and pressure'
  if (!design?.engineOk) {
    return <Empty title={title} text="Needs a successful design calculation (element datasheet values are required)." />
  }
  const pu = unitsFor(units, unitSet).pressure
  const data: { name: string; flux: number; pressure: number | null }[] = []
  for (const p of design.passes) for (const s of p.stages) for (const e of s.elements) {
    data.push({ name: `${design.passes.length > 1 ? `P${p.pass}-` : ''}S${s.stage}-E${e.position}`, flux: e.fluxGfd, pressure: pressureToDisplay(units, e.feedPressure, pu) })
  }
  return (
    <figure className="rounded-lg border border-border bg-panel p-3">
      <figcaption className="mb-2 text-sm font-semibold">{title}</figcaption>
      <div className="grid gap-2 sm:grid-cols-2">
        {([
          ['flux', 'Flux (gfd)', 'var(--series-1)', 1],
          ['pressure', `Feed pressure (${pu})`, 'var(--series-2)', 1],
        ] as const).map(([key, label, color, dp]) => (
          <div key={key}>
            <p className="text-xs text-muted">{label}</p>
            <div className="h-56">
              <ResponsiveContainer>
                <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  {GRID}
                  <XAxis dataKey="name" {...AXIS} interval="preserveStartEnd" />
                  <YAxis {...AXIS} width={48} domain={['auto', 'auto']} />
                  <Tooltip {...TOOLTIP_STYLE} cursor={{ stroke: 'var(--muted)' }} formatter={(v: number) => fmt(v, dp)} />
                  <Line type="monotone" dataKey={key} name={label} stroke={color} strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </div>
    </figure>
  )
}
