import { useCallback, useState } from 'react'
import { api } from './api/client'
import { useProjectStore } from './store/projectStore'

/** Wrap an async action with busy / error state. */
export function useAction<A extends unknown[]>(fn: (...args: A) => Promise<void>) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = useCallback(async (...args: A) => {
    setBusy(true)
    setError(null)
    try {
      await fn(...args)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }, [fn])
  return { run, busy, error }
}

/** Recalculate every page from the current project (used on load and by "Recalculate all"). */
export async function recalculateAll() {
  const { project, setAllResults } = useProjectStore.getState()
  const r = await api.calculateAll(project)
  setAllResults({ water: r.water, scaling: r.scaling, design: r.design })
}
