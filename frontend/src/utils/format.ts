/** Format a number for display. null/undefined/NaN -> fallback (default "N/A"). */
export function fmt(v: number | null | undefined, dp = 2, fallback = 'N/A'): string {
  if (v === null || v === undefined || Number.isNaN(v)) return fallback
  // round half up like Vontron (toFixed has binary-float surprises for e.g. 1.005)
  const f = 10 ** dp
  const r = Math.sign(v) * Math.round(Math.abs(v) * f + 1e-9) / f
  return r.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp })
}

/** Plain number string without thousands separators (for inputs). */
export function num(v: number | null | undefined, dp = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return ''
  const f = 10 ** dp
  return String(Math.round(v * f) / f)
}

export function parseNum(s: string): number | null {
  const t = s.trim().replace(/,/g, '')
  if (t === '' || t === '-' || t === '.') return null
  const v = Number(t)
  return Number.isFinite(v) ? v : null
}

/** `{ProjectName}_{YYYYMMDD}.{ext}` */
export function fileName(projectName: string, date: string, ext: string): string {
  const name = (projectName || 'Project').replace(/[^A-Za-z0-9 _-]/g, '').trim().replace(/\s+/g, '_') || 'Project'
  const d = (date || new Date().toISOString().slice(0, 10)).replace(/-/g, '')
  return `${name}_${d}.${ext}`
}

export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
