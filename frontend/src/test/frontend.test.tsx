import { fireEvent, render, screen } from '@testing-library/react'
import { IonGrid } from '../components/IonGrid'
import { MessagesPanel } from '../components/MessagesPanel'
import { defaultProject, isStale, normalizeProject, signature, useProjectStore } from '../store/projectStore'
import type { IonConstants, IonKey } from '../types'
import { fileName, fmt } from '../utils/format'
import { flowFromDisplay, flowToDisplay, fromMgL, toMgL } from '../utils/units'

const units = {
  gpmToM3h: 0.2271, gpmToGpd: 1440, m3hToM3d: 24, barToPsi: 14.504, ft2ToM2: 0.0929, gfdToLmh: 1.698,
  unitSets: {
    gpd_psi: { flow: 'gpd', pressure: 'psi' }, gpm_psi: { flow: 'gpm', pressure: 'psi' },
    m3h_bar: { flow: 'm3/h', pressure: 'bar' }, m3d_bar: { flow: 'm3/d', pressure: 'bar' },
  },
} as const

const ionConstants: IonConstants = {
  ions: {
    Na: { group: 'cation', charge: 1, eqWt: 23.0, caco3Factor: 2.18, molWt: 22.99 },
    Ca: { group: 'cation', charge: 2, eqWt: 20.04, caco3Factor: 2.5, molWt: 40.078 },
    SiO2: { group: 'neutral', charge: 0, eqWt: null, caco3Factor: null, molWt: 60.08 },
  } as IonConstants['ions'],
  order: ['Na', 'Ca', 'SiO2'] as IonKey[],
  rounding: { roundMgLTo2Decimals: true, mgLDecimals: 2 },
  validation: { temperatureC: { min: 1, max: 45 }, pH: { min: 1, max: 13 } },
}

describe('format', () => {
  it('rounds half up and shows N/A for null', () => {
    expect(fmt(1714.505, 2)).toBe('1,714.51')
    expect(fmt(-1.45, 1)).toBe('-1.5')
    expect(fmt(null)).toBe('N/A')
  })
  it('builds report file names', () => {
    expect(fileName('Plant A', '2026-11-08', 'pdf')).toBe('Plant_A_20261108.pdf')
    expect(fileName('', '2026-01-02', 'json')).toBe('Project_20260102.json')
  })
})

describe('units', () => {
  it('converts flows for display and back', () => {
    expect(flowToDisplay(units as never, 0.2271, 'gpm')).toBeCloseTo(1)
    expect(flowToDisplay(units as never, 0.2271, 'gpd')).toBeCloseTo(1440)
    expect(flowFromDisplay(units as never, 5, 'gpm')).toBeCloseTo(1.1355)
  })
  it('converts typed ion values to mg/L like Vontron', () => {
    expect(toMgL(ionConstants, 'Ca', 200, 'ppmCaCO3')).toBe(80)
    expect(toMgL(ionConstants, 'Na', 8.02, 'meq/L')).toBe(184.46)
    expect(fromMgL(ionConstants, 'SiO2', 20, 'meq/L')).toBeNull()
  })
})

describe('project store', () => {
  it('detects stale results', () => {
    const p = defaultProject()
    const sig = { water: signature(p, 'water') }
    p.results.water = {} as never
    expect(isStale(p, sig, 'water')).toBe(false)
    p.water.pH = 8
    expect(isStale(p, sig, 'water')).toBe(true)
  })
  it('normalizes an uploaded file and drops cached results', () => {
    const p = normalizeProject({ water: { pH: 7.6, ions: { Na: 150 } }, design: { recoveryPct: 50 }, results: { water: { tds: 1 } } })
    expect(p.water.ions.Na).toBe(150)
    expect(p.water.ions.Ca).toBe(0)
    expect(p.design.passes[0].stages[0].elementModel).toBe('LP22-8040')
    expect(p.results.water).toBeNull()
  })
  it('rejects files that are not projects', () => {
    expect(() => normalizeProject({ foo: 1 })).toThrow()
  })
  it('persists to localStorage', () => {
    useProjectStore.getState().setWater({ pH: 8.1 })
    expect(localStorage.getItem('ro-design-project')).toContain('8.1')
  })
})

describe('components', () => {
  it('shows warnings in the messages panel', () => {
    render(<MessagesPanel messages={[{ level: 'warning', text: 'Warning:Ions out of Balance.' }]} />)
    expect(screen.getByText('Warning:Ions out of Balance.')).toBeInTheDocument()
  })
  it('only lets the selected unit column be edited; neutral ions show n.a', () => {
    const onChange = vi.fn()
    render(
      <IonGrid title="Ions" ions={['Na', 'SiO2']} mgL={{ Na: 150, SiO2: 20 } as Record<IonKey, number>} analysis={null}
        constants={ionConstants} inputUnit="ppmCaCO3" locked={false} onChange={onChange} />,
    )
    const inputs = screen.getAllByRole('textbox')
    expect(inputs).toHaveLength(1) // Na ppm only (SiO2 has no ppm column)
    expect(screen.getAllByText('n.a')).toHaveLength(2)
    fireEvent.focus(inputs[0])
    fireEvent.change(inputs[0], { target: { value: '200' } })
    fireEvent.blur(inputs[0])
    expect(onChange).toHaveBeenCalledWith('Na', 91.74)
  })
})
