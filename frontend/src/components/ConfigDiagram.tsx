import type { DesignInput } from '../types'

/** System configuration diagram: pump -> stages (vessel banks) per pass, permeate and concentrate lines. */
export function ConfigDiagram({ design }: { design: DesignInput }) {
  const stageW = 110
  const gap = 46
  const passGap = 70
  const vesselH = 14
  const passes = design.passes
  const maxVessels = Math.min(Math.max(...passes.flatMap((p) => p.stages.map((s) => s.vessels)), 1), 8)
  const bankH = maxVessels * (vesselH + 4)
  const top = 30
  const midY = top + bankH / 2
  let x = 10
  const items: JSX.Element[] = []

  passes.forEach((p, pi) => {
    // pump
    items.push(
      <g key={`pump${pi}`}>
        <circle cx={x + 14} cy={midY} r={13} fill="none" stroke="var(--ink)" strokeWidth={1.5} />
        <path d={`M${x + 6} ${midY + 7} L${x + 22} ${midY} L${x + 6} ${midY - 7}`} fill="none" stroke="var(--ink)" strokeWidth={1.5} />
        <text x={x + 14} y={top + bankH + 26} textAnchor="middle" fontSize={10} fill="var(--muted)">
          {passes.length > 1 ? `Pass ${pi + 1}` : 'Pump'}
        </text>
      </g>,
    )
    if (design.recycle.enabled && pi === 0) {
      items.push(<text key="rec" x={x} y={14} fontSize={10} fill="var(--series-2)">↺ recycle</text>)
    }
    x += 28
    p.stages.forEach((s, si) => {
      items.push(<line key={`in${pi}${si}`} x1={x} y1={midY} x2={x + gap} y2={midY} stroke="var(--series-1)" strokeWidth={2} />)
      x += gap
      const n = Math.min(s.vessels, 8)
      const h = n * (vesselH + 4) - 4
      const y0 = midY - h / 2
      for (let v = 0; v < n; v++) {
        items.push(
          <rect key={`v${pi}${si}${v}`} x={x} y={y0 + v * (vesselH + 4)} width={stageW} height={vesselH} rx={7}
            fill="var(--panel)" stroke="var(--ink)" strokeWidth={1.2} />,
        )
      }
      items.push(
        <text key={`t${pi}${si}`} x={x + stageW / 2} y={top + bankH + 14} textAnchor="middle" fontSize={10} fill="var(--ink)">
          Stage {si + 1}: {s.vessels} × {s.elementsPerVessel}
        </text>,
        <text key={`m${pi}${si}`} x={x + stageW / 2} y={top + bankH + 26} textAnchor="middle" fontSize={9} fill="var(--muted)">
          {p.sameElementInPass ? p.stages[0].elementModel : s.elementModel}
        </text>,
        // permeate drop
        <line key={`p${pi}${si}`} x1={x + stageW / 2} y1={y0} x2={x + stageW / 2} y2={top - 6} stroke="var(--series-3)" strokeWidth={2} />,
      )
      x += stageW
    })
    items.push(<line key={`c${pi}`} x1={x} y1={midY} x2={x + 30} y2={midY} stroke="var(--series-2)" strokeWidth={2} />)
    x += 30 + (pi < passes.length - 1 ? passGap - 30 : 0)
  })
  const width = x + 10
  const height = top + bankH + 36
  return (
    // natural size up to 1.6x, never stretched to fill a wide card
    <svg viewBox={`0 0 ${width + 70} ${height}`} className="h-auto w-full" style={{ maxWidth: (width + 70) * 1.6 }}
      role="img" aria-label="System configuration diagram">
      <line x1={10} y1={top - 6} x2={width - 10} y2={top - 6} stroke="var(--series-3)" strokeWidth={2} />
      <text x={width - 6} y={top - 3} fontSize={10} fill="var(--muted)">Permeate</text>
      <text x={width - 6} y={midY + 3} fontSize={10} fill="var(--muted)">Concentrate</text>
      {items}
    </svg>
  )
}
