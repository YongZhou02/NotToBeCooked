/**
 * MILESTONE rows -> what the roadmap widget and modal draw -- Gantt r54/r55.
 *
 * Kept out of React so it can be tested without a DOM. The widget was built
 * against a hand-written mock (`w`, `n`, `s`), so this is the one place that
 * knows how the backend's names map onto it.
 */

import type { MilestoneRead } from "@workspace/contracts"

import type { Milestone } from "../types/course"

/** Ordered as the backend orders them (position), with the first unfinished one marked as "now". */
export function toUiRoadmap(rows: MilestoneRead[]): Milestone[] {
  const sorted = [...rows].sort((a, b) => a.position - b.position)
  const nowId = sorted.find((row) => row.status !== "completed")?.id

  return sorted.map((row) => ({
    id: row.id,
    w: row.week === null ? "" : `W${row.week}`,
    n: row.title,
    s: row.status === "completed" ? 1 : 0,
    now: row.id === nowId,
  }))
}

/**
 * A tick toggles between done and not started. `in_progress` is a backend state
 * the checklist cannot show, so ticking it completes it rather than clearing it.
 */
export function toggledStatus(
  status: MilestoneRead["status"]
): MilestoneRead["status"] {
  return status === "completed" ? "not_started" : "completed"
}

/** New milestones go to the end of the list. */
export function nextPosition(rows: MilestoneRead[]): number {
  return rows.reduce((max, row) => Math.max(max, row.position + 1), 0)
}
