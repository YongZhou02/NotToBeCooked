import { useCallback, useEffect, useMemo, useReducer, useState } from "react"
import { api } from "@workspace/contracts"

import {
  fileContentReducer,
  type FileContentState,
} from "../lib/fileContent"

/**
 * Fetch one file's bytes and hand back a URL the viewer can point at -- r78.
 *
 * Two things this owns that a component should not have to remember:
 *
 * - **Revoking the object URL.** `URL.createObjectURL` pins the blob in memory
 *   until the URL is revoked. A reader that opens twenty documents and revokes
 *   none holds all twenty for the life of the tab.
 * - **Ignoring stale answers.** The race is real as soon as there are tabs; the
 *   guard lives in `fileContentReducer` so it can be tested without a DOM.
 */
export function useFileContent(fileId: string | null, enabled = true) {
  const [state, dispatch] = useReducer(fileContentReducer, {
    status: "idle",
  } as FileContentState)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!fileId || !enabled) {
      dispatch({ type: "reset" })
      return
    }

    let cancelled = false
    dispatch({ type: "load", fileId })

    api.files
      .content(fileId)
      .then((blob) => {
        if (!cancelled) dispatch({ type: "loaded", fileId, blob })
      })
      .catch((error: unknown) => {
        if (!cancelled) dispatch({ type: "failed", fileId, error })
      })

    return () => {
      cancelled = true
    }
  }, [fileId, enabled, attempt])

  // Derived, not stored. Holding the URL in state meant setting state from
  // inside an effect, which is a cascading render and which the lint rule
  // rejects; the effect below only revokes.
  const url = useMemo(
    () => (state.status === "ready" ? URL.createObjectURL(state.blob) : null),
    [state]
  )

  useEffect(() => {
    if (!url) return
    return () => URL.revokeObjectURL(url)
  }, [url])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  return { state, url, retry }
}
