import { useCallback, useEffect, useRef, useState } from "react"

import { persistChanges, type Persisted } from "./storage"

export interface EvalStore {
  state: Persisted
  /**
   * Applies a change, saves it and returns the new state straight away, so a
   * caller can look at the result in the same step.
   */
  update: (change: (current: Persisted) => Persisted) => Persisted
}

/**
 * Holds the edits. `save` writes them to the person's team file; without it
 * (no dev server) they go to localStorage as before.
 */
export function useEvalStore(
  initial: Persisted,
  save?: (state: Persisted) => void
): EvalStore {
  const [state, setState] = useState<Persisted>(initial)
  const latest = useRef(state)
  const saveRef = useRef(save)
  useEffect(() => {
    saveRef.current = save
  }, [save])

  const update = useCallback((change: (current: Persisted) => Persisted) => {
    const before = latest.current
    const after = change(before)
    if (after === before) return before
    if (saveRef.current) saveRef.current(after)
    else persistChanges(before, after)
    latest.current = after
    setState(after)
    return after
  }, [])

  return { state, update }
}
