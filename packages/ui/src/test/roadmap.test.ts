import { describe, it } from "node:test"
import assert from "node:assert/strict"
import type { MilestoneRead } from "@workspace/contracts"
import { nextPosition, toggledStatus, toUiRoadmap } from "../lib/roadmap.ts"

function row(
  id: string,
  position: number,
  status: MilestoneRead["status"],
  week: number | null = null
): MilestoneRead {
  return {
    id,
    course_id: "c",
    position,
    title: `Milestone ${id}`,
    description: "",
    week,
    status,
    due_date: null,
    file_ids: [],
    created_at: "2026-10-10T00:00:00Z",
    updated_at: "2026-10-10T00:00:00Z",
  }
}

describe("roadmap mapping", () => {
  it("orders by position, not by the order the API returned", () => {
    const ui = toUiRoadmap([
      row("b", 2, "not_started"),
      row("a", 1, "not_started"),
    ])
    assert.deepEqual(
      ui.map((m) => m.id),
      ["a", "b"]
    )
  })

  it("marks only the first unfinished milestone as now", () => {
    const ui = toUiRoadmap([
      row("a", 0, "completed"),
      row("b", 1, "in_progress"),
      row("c", 2, "not_started"),
    ])
    assert.deepEqual(
      ui.map((m) => [m.s, m.now]),
      [
        [1, false],
        [0, true],
        [0, false],
      ]
    )
  })

  it("shows the week only when there is one", () => {
    const ui = toUiRoadmap([
      row("a", 0, "not_started", 3),
      row("b", 1, "not_started"),
    ])
    assert.deepEqual(
      ui.map((m) => m.w),
      ["W3", ""]
    )
  })

  it("ticking an in-progress milestone completes it", () => {
    assert.equal(toggledStatus("in_progress"), "completed")
    assert.equal(toggledStatus("completed"), "not_started")
  })

  it("appends new milestones after the last position", () => {
    assert.equal(nextPosition([]), 0)
    assert.equal(
      nextPosition([row("a", 4, "completed"), row("b", 1, "completed")]),
      5
    )
  })
})
