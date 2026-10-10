import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@workspace/contracts"

import { nextPosition, toggledStatus, toUiRoadmap } from "../lib/roadmap"

/** The course's milestones, and the three edits the roadmap modal offers. */
export function useRoadmap(courseId: string) {
  const queryClient = useQueryClient()
  const queryKey = ["courses", courseId, "milestones"]

  const milestonesQuery = useQuery({
    queryKey,
    queryFn: () => api.milestones.list(courseId),
    enabled: Boolean(courseId),
  })

  const rows = useMemo(() => milestonesQuery.data ?? [], [milestonesQuery.data])
  const roadmap = useMemo(() => toUiRoadmap(rows), [rows])

  const refresh = () => queryClient.invalidateQueries({ queryKey })

  const toggleMutation = useMutation({
    mutationFn: (milestoneId: string) => {
      const row = rows.find((r) => r.id === milestoneId)
      if (!row) throw new Error("Milestone not found")
      return api.milestones.update(courseId, milestoneId, {
        status: toggledStatus(row.status),
      })
    },
    onSuccess: refresh,
  })

  const addMutation = useMutation({
    mutationFn: ({ title, week }: { title: string; week: number | null }) =>
      api.milestones.create(courseId, {
        title,
        // Required by the generated type although the backend defaults it.
        description: "",
        week,
        position: nextPosition(rows),
      }),
    onSuccess: refresh,
  })

  const deleteMutation = useMutation({
    mutationFn: (milestoneId: string) =>
      api.milestones.delete(courseId, milestoneId),
    onSuccess: refresh,
  })

  const total = roadmap.length
  const done = roadmap.filter((m) => m.s === 1).length
  const pct = total ? Math.round((done / total) * 100) : 0
  const nowItem = roadmap.find((m) => m.now)
  const nextText = total
    ? nowItem
      ? nowItem.n
      : "all clear"
    : "no milestones yet"

  return {
    roadmap,
    stats: { done, total, pct, nextText },
    isLoading: milestonesQuery.isLoading,
    isError: milestonesQuery.isError,
    toggle: toggleMutation.mutateAsync,
    add: addMutation.mutateAsync,
    remove: deleteMutation.mutateAsync,
    isSaving:
      toggleMutation.isPending ||
      addMutation.isPending ||
      deleteMutation.isPending,
  }
}
