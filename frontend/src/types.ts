// Project data model (prompt section 3). Internal units: mg/L, °C, m³/h, bar.
export const ION_KEYS = ['Na', 'Ca', 'Mg', 'K', 'Ba', 'Sr', 'NH4', 'B', 'Cl', 'CO3', 'HCO3', 'F', 'NO3', 'SO4', 'SiO2'] as const
export type IonKey = (typeof ION_KEYS)[number]
export type InputUnit = 'mg/L' | 'ppmCaCO3' | 'meq/L'
export type ScalingOption = 'none' | 'ph_adjust' | 'softening' | 'antiscalant'
export type UnitSet = 'gpd_psi' | 'gpm_psi' | 'm3h_bar' | 'm3d_bar'

export interface Water {
  inputUnit: InputUnit
  specifyIndividualSolutes: boolean
  tdsInput: number | null
  temperatureC: number
  pH: number
  waterType: string
  ions: Record<IonKey, number>
}

export interface ScalingInput {
  recoveryPct: number
  temperatureC: number
  option: ScalingOption
  phAdjust: { chemical: 'H2SO4' | 'HCl'; targetPH: number }
  softening: { caLeakage: number; mgLeakage: number }
}

export interface Stage {
  vessels: number
  elementsPerVessel: number
  elementModel: string
  backPressure: number
}
export interface Pass {
  stages: Stage[]
  sameElementInPass: boolean
  sameBackPressure: boolean
}

export interface DesignInput {
  unitSet: UnitSet
  recoveryPct: number
  permeateFlow: number
  feedTempC: number
  foulingFactor: number
  passes: Pass[]
  pumpEfficiencyEnabled: boolean
  pumpEfficiencyPct: number
  intakeBothEnds: boolean
  frontEndPct: number
  recycle: { enabled: boolean; flow: number }
}

export interface Project {
  version: string
  project: { name: string; date: string; designedBy: string; company: string }
  water: Water
  scaling: ScalingInput
  design: DesignInput
  results: Results
}

export interface Message {
  level: 'info' | 'warning' | 'error'
  text: string
  page?: string
}

export interface IonRow { mgL: number; ppmCaCO3: number | null; meq: number | null; group: string }
export interface WaterResult {
  rows: Record<IonKey, IonRow>
  order: IonKey[]
  ionsMgL: Record<IonKey, number>
  tds: number
  cations: number
  anions: number
  balance: number
  imbalance: boolean
  messages: Message[]
}

export interface ScalingColumn {
  pH: number
  TDS: number
  HCO3: number
  CO3: number
  CO2: number
  LSI: number | null
  SDSI: number | null
  ionicStrength: number
  CaSO4: number | null
  BaSO4: number | null
  SrSO4: number | null
  CaF2: number | null
  SiO2: number | null
  ions: Record<IonKey, number>
}
export interface IndexStatus { value: number | null; limit: number; status: 'green' | 'amber' | 'red' | 'n/a'; index?: string }
export interface ScalingResult {
  cf: number
  recoveryPct: number
  temperatureC: number
  option: ScalingOption
  columns: { feed: ScalingColumn; adjusted: ScalingColumn; concentrate: ScalingColumn }
  acidDose: { chemical: string; meqPerL: number; mgL: number } | null
  status: Record<string, IndexStatus>
  messages: Message[]
}

export interface ElementResult {
  position: number
  model: string
  feedFlow: number
  permeateFlow: number
  concentrateFlow: number
  recoveryPct: number
  feedPressure: number
  concentratePressure: number
  pressureDrop: number
  ndp: number
  fluxGfd: number
  fluxLmh: number
  feedTDS: number
  permeateTDS: number
  concentrateTDS: number
}
export interface StageResult {
  stage: number
  vessels: number
  elementsPerVessel: number
  elementModel: string
  backPressure: number
  boosterPressure?: number
  feedFlow: number | null
  permeateFlow?: number
  concentrateFlow?: number
  feedPressure?: number
  concentratePressure?: number
  pressureDrop?: number
  fluxGfd?: number
  permeateTDS?: number
  concentrateTDS?: number
  elements: ElementResult[]
}
export interface PassResult { pass: number; feedFlow: number; permeateFlow: number; feedPressure?: number; pumpKw?: number; stages: StageResult[] }
export interface DesignSystemResult {
  feedFlow: number | null
  permeateFlow: number | null
  concentrateFlow: number | null
  recoveryPct: number | null
  totalElements: number | null
  fluxGfd: number | null
  fluxLmh: number | null
  feedPressure: number | null
  pumpKw: number | null
  specificEnergy: number | null
  feedTDS: number | null
  permeateTDS: number | null
  concentrateTDS: number | null
  recycleFlow: number
  feedIons: Record<IonKey, number> | null
  permeateIons: Record<IonKey, number> | null
  concentrateIons: Record<IonKey, number> | null
}
export interface DesignResult {
  system: DesignSystemResult
  passes: PassResult[]
  messages: Message[]
  engineOk: boolean
}

export interface Results {
  water?: WaterResult | null
  scaling?: ScalingResult | null
  design?: DesignResult | null
}

// Reference data from the backend config
export interface IonConstant { group: string; charge: number; eqWt: number | null; caco3Factor: number | null; molWt: number }
export interface IonConstants {
  ions: Record<IonKey, IonConstant>
  order: IonKey[]
  rounding: { roundMgLTo2Decimals: boolean; mgLDecimals: number }
  validation: { temperatureC: { min: number; max: number }; pH: { min: number; max: number } }
}
export interface UnitConstants {
  gpmToM3h: number
  gpmToGpd: number
  m3hToM3d: number
  barToPsi: number
  ft2ToM2: number
  gfdToLmh: number
  unitSets: Record<UnitSet, { flow: FlowUnit; pressure: PressureUnit }>
}
export type FlowUnit = 'gpd' | 'gpm' | 'm3/h' | 'm3/d'
export type PressureUnit = 'psi' | 'bar'
export interface ElementSpec { model: string; areaFt2: number; [k: string]: unknown }
export interface WaterTypeInfo { name: string; limits: Record<string, unknown> }
export interface Constants {
  ions: IonConstants
  units: UnitConstants
  elements: ElementSpec[]
  waterTypes: WaterTypeInfo[]
}
