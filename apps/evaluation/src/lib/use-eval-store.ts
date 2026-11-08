import { useCallback, useRef, useState } from "react"

import { loadPersisted, persistChanges, type Persisted } from "./storage"

export interface EvalStore {
  state: Persisted
  /**
   * Applies a change, saves what changed to localStorage and returns the new
   * state straight away, so a caller can look at the result in the same step.
   */
  update: (change: (current: Persisted) => Persisted) => Persisted
}

export function useEvalStore(): EvalStore {
  const [state, setState] = useState<Persisted>(loadPersisted)
  const latest = useRef(state)

  const update = useCallback((change: (current: Persisted) => Persisted) => {
    const before = latest.current
    const after = change(before)
    if (after === before) return before
    persistChanges(before, after)
    latest.current = after
    setState(after)
    return after
  }, [])

  return { state, update }
}
