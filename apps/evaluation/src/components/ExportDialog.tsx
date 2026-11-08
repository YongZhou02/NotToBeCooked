import { useState } from "react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import type { ResolvedQuestion } from "@/lib/questions"
import { Chip } from "./bits"

/**
 * Choose which questions to share. It starts from the questions the filters
 * show, all ticked. "Human-written only" unticks every question a person did
 * not write and keeps them out of the file.
 */
export function ExportDialog({
  questions,
  onExport,
  onClose,
}: {
  /** The questions the filters show. */
  questions: ResolvedQuestion[]
  onExport: (selected: ResolvedQuestion[]) => void
  onClose: () => void
}) {
  const [selection, setSelection] = useState(
    () => new Set(questions.map((q) => q.id))
  )
  const [humanOnly, setHumanOnly] = useState(false)
  // The ticks that "Human-written only" took away, put back when it is turned off.
  const [beforeHumanOnly, setBeforeHumanOnly] = useState<Set<string> | null>(
    null
  )

  const isHuman = (q: ResolvedQuestion) => q.origin === "human"
  const eligible = (q: ResolvedQuestion) => !humanOnly || isHuman(q)
  const chosen = questions.filter((q) => selection.has(q.id) && eligible(q))
  const count = chosen.length

  const toggleHumanOnly = (on: boolean) => {
    setHumanOnly(on)
    if (on) {
      setBeforeHumanOnly(new Set(selection))
      setSelection(
        new Set(
          questions
            .filter((q) => isHuman(q) && selection.has(q.id))
            .map((q) => q.id)
        )
      )
    } else if (beforeHumanOnly) {
      setSelection(beforeHumanOnly)
      setBeforeHumanOnly(null)
    }
  }

  const toggle = (id: string, on: boolean) =>
    setSelection((current) => {
      const next = new Set(current)
      if (on) next.add(id)
      else next.delete(id)
      return next
    })

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        data-testid="export-dialog"
        className="flex max-h-[calc(100dvh-2rem)] flex-col gap-3 sm:max-w-2xl"
      >
        <DialogHeader>
          <p className="text-[11px] font-semibold tracking-widest text-(--tx-dim) uppercase">
            Share with a teammate
          </p>
          <DialogTitle className="text-lg">Export questions</DialogTitle>
          <DialogDescription>
            Listing the questions your filters show. Untick anything you do not
            want to share.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() =>
              setSelection(new Set(questions.filter(eligible).map((q) => q.id)))
            }
          >
            Select all
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setSelection(new Set())}
          >
            Select none
          </Button>
          <label
            className="ml-auto flex cursor-pointer items-center gap-1.5 text-sm font-semibold"
            title="Untick every AI-written question and export only the ones people wrote"
          >
            <input
              type="checkbox"
              id="exportHumanOnly"
              checked={humanOnly}
              onChange={(e) => toggleHumanOnly(e.target.checked)}
              className="accent-(--acc)"
            />
            Human-written only
          </label>
          <Chip data-testid="export-count">{count} selected</Chip>
        </div>

        <ul className="min-h-0 flex-1 overflow-y-auto rounded-md border border-(--line)">
          {questions.length === 0 && (
            <li className="p-3 text-sm text-muted-foreground">
              No questions match the current filters.
            </li>
          )}
          {questions.map((q) => (
            <li
              key={q.id}
              className="border-b border-(--line-soft) last:border-b-0"
            >
              <label className="flex cursor-pointer items-start gap-2 p-2 hover:bg-(--bg-hover)">
                <input
                  type="checkbox"
                  aria-label={`Export ${q.id}`}
                  checked={selection.has(q.id) && eligible(q)}
                  disabled={!eligible(q)}
                  onChange={(e) => toggle(q.id, e.target.checked)}
                  className="mt-1 accent-(--acc)"
                />
                <span
                  className={`flex min-w-0 flex-1 flex-wrap items-center gap-1.5 ${eligible(q) ? "" : "opacity-50"}`}
                >
                  <span className="rounded border border-(--line) bg-(--bg-raise) px-1.5 font-mono text-xs font-bold text-(--tx-dim)">
                    {q.id}
                  </span>
                  {isHuman(q) && <Chip tone="accent">Human</Chip>}
                  {q.is_hard_case && <Chip tone="warn">Hard</Chip>}
                  <span className="min-w-0 flex-1 basis-48 text-sm [overflow-wrap:anywhere]">
                    {q.question}
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>

        <DialogFooter>
          <Button
            type="button"
            id="exportConfirmBtn"
            disabled={count === 0}
            onClick={() => onExport(chosen)}
          >
            Export {count} question{count === 1 ? "" : "s"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
