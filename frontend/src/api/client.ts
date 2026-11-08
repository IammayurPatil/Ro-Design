import type {
  Constants, DesignResult, ElementSpec, IonConstants, Message, Project, ScalingInput, ScalingResult,
  UnitConstants, Water, WaterResult, WaterTypeInfo,
} from '../types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

export class ApiError extends Error {}

async function request<T>(path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Cannot reach the calculation server. Is the backend running?')
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const j = await res.json()
      if (j.detail) detail = Array.isArray(j.detail) ? j.detail.map((d: { msg: string }) => d.msg).join('; ') : String(j.detail)
    } catch { /* not JSON */ }
    throw new ApiError(`The server rejected the request: ${detail}`)
  }
  return res.json() as Promise<T>
}

async function download(path: string, body: unknown): Promise<Blob> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  } catch {
    throw new ApiError('Cannot reach the calculation server. Is the backend running?')
  }
  if (!res.ok) throw new ApiError(`Report failed: ${res.status} ${res.statusText}`)
  return res.blob()
}

export interface AllResults { water: WaterResult; scaling: ScalingResult; design: DesignResult; messages: Message[] }

export const api = {
  analyzeWater: (water: Water) => request<WaterResult>('/api/water/analyze', water),
  autoBalance: (water: Water) => request<{ water: Water; analysis: WaterResult }>('/api/water/auto-balance', water),
  calculateScaling: (water: Water, scaling: ScalingInput) => request<ScalingResult>('/api/scaling/calculate', { water, scaling }),
  calculateDesign: (project: Project) => request<DesignResult>('/api/design/calculate', stripResults(project)),
  calculateAll: (project: Project) => request<AllResults>('/api/calculate-all', stripResults(project)),
  reportPdf: (project: Project) => download('/api/report/pdf', stripResults(project)),
  reportXlsx: (project: Project) => download('/api/report/xlsx', stripResults(project)),
  async constants(): Promise<Constants> {
    const [ions, units, elements, waterTypes] = await Promise.all([
      request<IonConstants>('/api/config/ions'),
      request<UnitConstants>('/api/config/units'),
      request<ElementSpec[]>('/api/elements'),
      request<WaterTypeInfo[]>('/api/water-types'),
    ])
    return { ions, units, elements, waterTypes }
  },
}

function stripResults(p: Project) {
  return { ...p, results: {} }
}
