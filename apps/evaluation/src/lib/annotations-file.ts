import type { DashboardData } from "../types"
import {
  applyImport,
  buildExportPayload,
  getAllQuestions,
  setHumanIdPrefix,
} from "./questions"
import { emptyPersisted, loadPersisted, type Persisted } from "./storage"

/**
 * Where a person's edits are kept.
 *
 * "file": the dev server saves them to evaluation/datasets/cpt316/team/<name>.json,
 *   the file merge_team_questions.py reads. This is the normal case.
 * "browser": no server (the static build), so edits stay in localStorage
 *   as before and must be exported by hand.
 */
export type Backing =
  | { mode: "file"; reviewer: string; file: string; etag: string }
  | { mode: "browser" }

export type SaveStatus =
  | { state: "saved" }
  | { state: "saving" }
  | { state: "error"; message: string }
  | { state: "conflict"; message: string }

const ENDPOINT = "api/annotations"

interface ServerFile {
  reviewer: string
  file: string
  etag: string
  content: unknown
}

/** Ids of every question this person created or changed in any way. */
function touchedIds(p: Persisted): Set<string> {
  return new Set([
    ...p.customQuestions.map((q) => q.id),
    ...Object.keys(p.questionEdits),
    ...Object.keys(p.answerEdits),
    ...Object.keys(p.verifications),
    ...Object.keys(p.reviews),
  ])
}

/**
 * The team file: one row per touched question, in the export format, sorted
 * by id. No timestamp, so saving twice without a change writes the same bytes
 * and git shows no difference.
 */
export function buildTeamFile(
  p: Persisted,
  data: DashboardData,
  reviewer: string
) {
  const ids = touchedIds(p)
  const selected = getAllQuestions(p, data)
    .filter((q) => ids.has(q.id))
    .sort((a, b) => a.id.localeCompare(b.id))
  const { questions } = buildExportPayload(p, data, selected)
  return { dataset: data.dataset.name, reviewer, questions }
}

/**
 * Reads the person's file and turns it back into edits over the original
 * questions. A question already merged into the data is matched by id, so it
 * becomes an edit (or nothing), never a second copy.
 */
export async function loadBacking(
  data: DashboardData
): Promise<{ backing: Backing; initial: Persisted; migrated: boolean }> {
  let server: ServerFile | null = null
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}${ENDPOINT}`, {
      cache: "no-store",
    })
    const isJson = response.headers
      .get("content-type")
      ?.includes("application/json")
    if (response.ok && isJson) server = (await response.json()) as ServerFile
    else if (isJson) {
      const { error } = (await response.json()) as { error?: string }
      throw new Error(error ?? `HTTP ${response.status}`)
    }
  } catch (error) {
    if (error instanceof Error && !(error instanceof TypeError)) throw error
  }

  if (!server)
    return {
      backing: { mode: "browser" },
      initial: loadPersisted(),
      migrated: false,
    }

  setHumanIdPrefix(server.reviewer)
  const backing: Backing = {
    mode: "file",
    reviewer: server.reviewer,
    file: server.file,
    etag: server.etag,
  }

  if (server.content === null) {
    // First run with file saving: carry over whatever this browser held.
    const fromBrowser = loadPersisted()
    return {
      backing,
      initial: fromBrowser,
      migrated: touchedIds(fromBrowser).size > 0,
    }
  }

  const content = Array.isArray(server.content)
    ? { questions: server.content }
    : server.content
  const result = applyImport(emptyPersisted, data, content)
  if (!result.ok) throw new Error(`${server.file}: ${result.message}`)
  return { backing, initial: result.next, migrated: false }
}

/**
 * Saves one state at a time, always the newest. Edits made while a save is in
 * flight are folded into the next save instead of racing it. After a conflict
 * it stops, so it can never overwrite someone else's change.
 */
export class FileSaver {
  private etag: string
  private pending: unknown = null
  private running = false
  private stopped = false

  private onStatus: (status: SaveStatus) => void

  constructor(etag: string, onStatus: (status: SaveStatus) => void) {
    this.etag = etag
    this.onStatus = onStatus
  }

  get busy() {
    return this.running || this.pending !== null
  }

  save(content: unknown) {
    if (this.stopped) return
    this.pending = content
    this.onStatus({ state: "saving" })
    void this.flush()
  }

  private async flush() {
    if (this.running) return
    this.running = true
    try {
      while (this.pending !== null && !this.stopped) {
        const content = this.pending
        this.pending = null
        const response = await fetch(`${import.meta.env.BASE_URL}${ENDPOINT}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ etag: this.etag, content }),
        })
        const body = (await response.json().catch(() => ({}))) as {
          etag?: string
          error?: string
        }
        if (response.status === 409) {
          this.stopped = true
          this.onStatus({
            state: "conflict",
            message: body.error ?? "conflict",
          })
          return
        }
        if (!response.ok || !body.etag) {
          // Keep the unsaved state so the next edit retries it.
          this.pending ??= content
          this.onStatus({
            state: "error",
            message: body.error ?? `HTTP ${response.status}`,
          })
          return
        }
        this.etag = body.etag
      }
      if (!this.stopped) this.onStatus({ state: "saved" })
    } catch (error) {
      this.onStatus({ state: "error", message: String(error) })
    } finally {
      this.running = false
    }
  }
}
