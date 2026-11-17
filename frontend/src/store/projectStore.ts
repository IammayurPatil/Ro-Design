import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type {
  Constants, DesignInput, DesignResult, IonKey, Pass, Project, Results, ScalingInput, ScalingResult, Stage, Water,
  WaterResult,
} from '../types'
import { ION_KEYS } from '../types'

export const DEFAULT_ELEMENT = 'LP22-8040'

export function defaultStage(model = DEFAULT_ELEMENT): Stage {
  return { vessels: 1, elementsPerVessel: 1, elementModel: model, backPressure: 0 }
}

export function defaultPass(model = DEFAULT_ELEMENT): Pass {
  return { stages: [defaultStage(model)], sameElementInPass: true, sameBackPressure: true }
}

export function defaultProject(): Project {
  return {
    version: '1.0',
    project: { name: '', date: new Date().toISOString().slice(0, 10), designedBy: 'Untitled', company: 'Untitled' },
    water: {
      inputUnit: 'mg/L',
      specifyIndividualSolutes: true,
      tdsInput: null,
      temperatureC: 25,
      pH: 7.5,
      waterType: 'RO Permeate SDI < 1',
      ions: Object.fromEntries(ION_KEYS.map((k) => [k, 0])) as Record<IonKey, number>,
    },
    scaling: {
      recoveryPct: 15,
      temperatureC: 25,
      option: 'none',
      phAdjust: { chemical: 'H2SO4', targetPH: 7.5 },
      softening: { caLeakage: 0.1, mgLeakage: 0.1 },
    },
    design: {
      unitSet: 'gpm_psi',
      recoveryPct: 15,
      permeateFlow: 1.1355, // m³/h (= 5 gpm)
      feedTempC: 25,
      foulingFactor: 0.85,
      passes: [defaultPass()],
      pumpEfficiencyEnabled: false,
      pumpEfficiencyPct: 80,
      intakeBothEnds: false,
      frontEndPct: 50,
      recycle: { enabled: false, flow: 0 },
    },
    results: { water: null, scaling: null, design: null },
  }
}

type Section = 'water' | 'scaling' | 'design'

/** What each section's result depends on. Used for the "Out of date" badge. */
export function signature(p: Project, section: Section): string {
  if (section === 'water') return JSON.stringify(p.water)
  if (section === 'scaling') return JSON.stringify([p.water, p.scaling])
  return JSON.stringify([p.water, p.scaling, p.design])
}

/** Merge an uploaded / persisted project over the defaults so missing fields never crash the UI. */
export function normalizeProject(raw: unknown): Project {
  if (!raw || typeof raw !== 'object') throw new Error('The file is not a project.')
  const r = raw as Partial<Project>
  if (!r.water || !r.design) throw new Error('The file is not a project: "water" or "design" is missing.')
  const d = defaultProject()
  const passes = (r.design.passes?.length ? r.design.passes : d.design.passes).map((p) => ({
    ...defaultPass(),
    ...p,
    stages: (p.stages?.length ? p.stages : [defaultStage()]).map((s) => ({ ...defaultStage(), ...s })),
  }))
  return {
    version: r.version ?? d.version,
    project: { ...d.project, ...r.project },
    // Rule 6: TDS is never stored separately; it is recomputed from the ions.
    water: { ...d.water, ...r.water, ions: { ...d.water.ions, ...(r.water.ions ?? {}) } },
    scaling: {
      ...d.scaling, ...r.scaling,
      phAdjust: { ...d.scaling.phAdjust, ...r.scaling?.phAdjust },
      softening: { ...d.scaling.softening, ...r.scaling?.softening },
    },
    design: { ...d.design, ...r.design, passes, recycle: { ...d.design.recycle, ...r.design.recycle } },
    results: { water: null, scaling: null, design: null }, // a cache: always recalculated on load
  }
}

interface State {
  project: Project
  signatures: Partial<Record<Section, string>>
  constants: Constants | null
  setConstants: (c: Constants) => void
  setProjectInfo: (p: Partial<Project['project']>) => void
  setWater: (w: Partial<Water>) => void
  setIon: (ion: IonKey, mgL: number) => void
  setScaling: (s: Partial<ScalingInput>) => void
  setDesign: (d: Partial<DesignInput>) => void
  setPassCount: (n: number) => void
  setStageCount: (pass: number, n: number) => void
  updatePass: (pass: number, p: Partial<Pass>) => void
  updateStage: (pass: number, stage: number, s: Partial<Stage>) => void
  setWaterResult: (r: WaterResult) => void
  setScalingResult: (r: ScalingResult) => void
  setDesignResult: (r: DesignResult) => void
  setAllResults: (r: Required<Results>) => void
  newProject: () => void
  loadProject: (raw: unknown) => void
}

export const useProjectStore = create<State>()(
  persist(
    (set) => ({
      project: defaultProject(),
      signatures: {},
      constants: null,
      setConstants: (constants) => set({ constants }),
      setProjectInfo: (p) => set((s) => ({ project: { ...s.project, project: { ...s.project.project, ...p } } })),
      setWater: (w) => set((s) => ({ project: { ...s.project, water: { ...s.project.water, ...w } } })),
      setIon: (ion, mgL) =>
        set((s) => ({
          project: { ...s.project, water: { ...s.project.water, ions: { ...s.project.water.ions, [ion]: mgL } } },
        })),
      setScaling: (sc) => set((s) => ({ project: { ...s.project, scaling: { ...s.project.scaling, ...sc } } })),
      setDesign: (d) => set((s) => ({ project: { ...s.project, design: { ...s.project.design, ...d } } })),
      setPassCount: (n) =>
        set((s) => {
          const passes = [...s.project.design.passes]
          while (passes.length < n) passes.push(defaultPass(passes[0]?.stages[0]?.elementModel))
          passes.length = n
          return { project: { ...s.project, design: { ...s.project.design, passes } } }
        }),
      setStageCount: (pi, n) =>
        set((s) => {
          const passes = s.project.design.passes.map((p, i) => {
            if (i !== pi) return p
            const stages = [...p.stages]
            while (stages.length < n) stages.push(defaultStage(stages[0]?.elementModel))
            stages.length = n
            return { ...p, stages }
          })
          return { project: { ...s.project, design: { ...s.project.design, passes } } }
        }),
      updatePass: (pi, patch) =>
        set((s) => ({
          project: {
            ...s.project,
            design: { ...s.project.design, passes: s.project.design.passes.map((p, i) => (i === pi ? { ...p, ...patch } : p)) },
          },
        })),
      updateStage: (pi, si, patch) =>
        set((s) => ({
          project: {
            ...s.project,
            design: {
              ...s.project.design,
              passes: s.project.design.passes.map((p, i) =>
                i !== pi ? p : { ...p, stages: p.stages.map((st, j) => (j === si ? { ...st, ...patch } : st)) }),
            },
          },
        })),
      setWaterResult: (r) =>
        set((s) => ({
          project: { ...s.project, results: { ...s.project.results, water: r } },
          signatures: { ...s.signatures, water: signature(s.project, 'water') },
        })),
      setScalingResult: (r) =>
        set((s) => ({
          project: { ...s.project, results: { ...s.project.results, scaling: r } },
          signatures: { ...s.signatures, scaling: signature(s.project, 'scaling') },
        })),
      setDesignResult: (r) =>
        set((s) => ({
          project: { ...s.project, results: { ...s.project.results, design: r } },
          signatures: { ...s.signatures, design: signature(s.project, 'design') },
        })),
      setAllResults: (r) =>
        set((s) => ({
          project: { ...s.project, results: r },
          signatures: {
            water: signature(s.project, 'water'),
            scaling: signature(s.project, 'scaling'),
            design: signature(s.project, 'design'),
          },
        })),
      newProject: () => set({ project: defaultProject(), signatures: {} }),
      loadProject: (raw) => set({ project: normalizeProject(raw), signatures: {} }),
    }),
    {
      name: 'ro-design-project',
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ project: s.project, signatures: s.signatures }),
      merge: (persisted, current) => {
        const p = persisted as Partial<State> | undefined
        if (!p?.project) return current
        try {
          return { ...current, project: normalizeProject(p.project), signatures: p.signatures ?? {} }
        } catch {
          return current
        }
      },
    },
  ),
)

export function isStale(project: Project, signatures: Partial<Record<Section, string>>, section: Section): boolean {
  const hasResult = !!project.results[section]
  return !hasResult || signatures[section] !== signature(project, section)
}
