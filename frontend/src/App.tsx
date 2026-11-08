import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api/client'
import { Button } from './components/ui'
import { recalculateAll } from './hooks'
import Dashboard from './pages/Dashboard'
import DesignSystem from './pages/DesignSystem'
import Report, { downloadProjectJson } from './pages/Report'
import Scaling from './pages/Scaling'
import WaterAnalysis from './pages/WaterAnalysis'
import { useProjectStore } from './store/projectStore'

const TABS = [
  { to: '/water', label: 'Water Analysis' },
  { to: '/scaling', label: 'Scaling' },
  { to: '/design', label: 'Design System' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/report', label: 'Report' },
]

export default function App() {
  const constants = useProjectStore((s) => s.constants)
  const setConstants = useProjectStore((s) => s.setConstants)
  const newProject = useProjectStore((s) => s.newProject)
  const loadProject = useProjectStore((s) => s.loadProject)
  const [startupError, setStartupError] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const boot = () => {
    setStartupError(null)
    api.constants()
      .then((c) => {
        setConstants(c)
        // results are a cache: always recalculate after a refresh
        return recalculateAll().catch(() => undefined)
      })
      .catch((e: Error) => setStartupError(e.message))
  }
  useEffect(boot, []) // eslint-disable-line react-hooks/exhaustive-deps

  const flash = (tone: 'ok' | 'error', text: string) => {
    setNotice({ tone, text })
    setTimeout(() => setNotice(null), 5000)
  }

  const onOpen = async (file: File) => {
    try {
      const data = JSON.parse(await file.text())
      loadProject(data)
      await recalculateAll()
      flash('ok', `Opened ${file.name}.`)
    } catch (e) {
      flash('error', `Could not open ${file.name}: ${(e as Error).message}`)
    }
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-border bg-panel/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
          <span className="font-semibold">RO Design</span>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => {
              if (window.confirm('Start a new project? Unsaved changes will be lost.')) {
                newProject()
                recalculateAll().catch(() => undefined)
              }
            }}>New</Button>
            <Button variant="secondary" onClick={() => fileRef.current?.click()}>Open project (.json)</Button>
            <Button variant="secondary" onClick={downloadProjectJson}>Save project (.json)</Button>
            <input ref={fileRef} type="file" accept=".json,application/json" className="hidden" aria-label="Open project file"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) onOpen(f); e.target.value = '' }} />
          </div>
          {notice && (
            <span role="status" className={clsx('text-sm', notice.tone === 'error' ? 'text-danger' : 'text-muted')}>{notice.text}</span>
          )}
        </div>
        <nav className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4">
          {TABS.map((t) => (
            <NavLink key={t.to} to={t.to}
              className={({ isActive }) => clsx('whitespace-nowrap border-b-2 px-3 py-2 text-sm',
                isActive ? 'border-accent font-semibold text-ink' : 'border-transparent text-muted hover:text-ink')}>
              {t.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-4">
        {startupError ? (
          <div className="rounded-lg border border-danger/40 bg-panel p-6 text-center">
            <p className="font-medium text-danger">{startupError}</p>
            <p className="mt-1 text-sm text-muted">Start the backend (see README), then try again.</p>
            <Button className="mt-4" onClick={boot}>Try again</Button>
          </div>
        ) : !constants ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
          <Routes>
            <Route path="/water" element={<WaterAnalysis />} />
            <Route path="/scaling" element={<Scaling />} />
            <Route path="/design" element={<DesignSystem />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/report" element={<Report />} />
            <Route path="*" element={<Navigate to="/water" replace />} />
          </Routes>
        )}
      </main>
    </div>
  )
}
