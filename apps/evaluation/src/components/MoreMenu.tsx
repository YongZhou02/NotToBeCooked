import { useEffect, useRef, useState } from "react"
import { ChevronDown } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { cn } from "@workspace/ui/lib/utils"
import type { AllMetrics, Filters } from "@/lib/questions"
import { Chip, Eyebrow } from "./bits"

type SplitFilter = Filters["split"]

/** The "More" menu: split composition (click one to filter by it) and Import. */
export function MoreMenu({
  metrics,
  split,
  sourceCount,
  onSplit,
  onImport,
}: {
  metrics: AllMetrics
  split: SplitFilter
  sourceCount: number
  onSplit: (split: SplitFilter) => void
  onImport: (file: File) => void
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  // The panel is an overlay; close it on any click outside it, or Escape.
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const cards: [string, SplitFilter, AllMetrics["dev"], string][] = [
    ["Dev split", "dev", metrics.dev, `${metrics.dev.questions} questions`],
    ["Test split", "test", metrics.test, `${metrics.test.questions} questions`],
    [
      "Stress split",
      "stress",
      metrics.stress,
      `${metrics.stress.questions} questions`,
    ],
    [
      "Entire corpus",
      "all",
      metrics.total,
      `${metrics.total.questions} total items`,
    ],
  ]

  return (
    <div ref={root} className="relative">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
      >
        More <ChevronDown />
      </Button>
      {open && (
        <div
          role="dialog"
          aria-label="More actions"
          className="fixed inset-x-2 top-28 z-40 grid max-h-[calc(100dvh-8rem)] gap-3 overflow-y-auto rounded-lg border border-(--line) bg-popover p-3 text-popover-foreground shadow-xl min-[1000px]:absolute min-[1000px]:inset-x-auto min-[1000px]:top-full min-[1000px]:right-0 min-[1000px]:mt-1 min-[1000px]:w-[36rem]"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <Eyebrow>Corpus contents</Eyebrow>
              <h3 className="text-base font-semibold">Split composition</h3>
            </div>
            <Chip>
              {metrics.total.questions} questions ·{" "}
              {metrics.total.golden_quotes} golden quotes
            </Chip>
          </div>

          <div className="grid gap-2 min-[560px]:grid-cols-2">
            {cards.map(([title, value, part, headline]) => (
              <button
                key={value}
                type="button"
                aria-pressed={split === value}
                onClick={() =>
                  onSplit(split === value && value !== "all" ? "all" : value)
                }
                className={cn(
                  "grid gap-0.5 rounded-md border p-2 text-left text-xs transition-colors hover:bg-(--bg-hover)",
                  split === value
                    ? "border-(--acc) bg-primary/10"
                    : "border-(--line)"
                )}
              >
                <span className="font-semibold text-muted-foreground uppercase">
                  {title}
                </span>
                <span className="text-sm font-semibold">{headline}</span>
                <span className="text-muted-foreground">
                  {part.golden_quotes} golden quotes
                  {value === "all"
                    ? ` across ${sourceCount} source PDF${sourceCount === 1 ? "" : "s"}`
                    : ` · ${part.evidence_groups} evidence groups`}
                </span>
                <span className="text-muted-foreground">
                  Answer keys: {part.verified} verified · {part.unverified}{" "}
                  unverified
                </span>
                <span className="text-muted-foreground">
                  {value === "all" ? "All authors" : "Authors"}:{" "}
                  {part.synthetic} AI-written | {part.human} human-written
                </span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <input
              ref={fileInput}
              type="file"
              id="importDatasetFile"
              accept=".json"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) {
                  setOpen(false)
                  onImport(file)
                }
                e.target.value = "" // so the same file can be imported again
              }}
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              title="Import a file exported from this dashboard"
              onClick={() => fileInput.current?.click()}
            >
              Import JSON
            </Button>
            <span className="text-xs text-muted-foreground">
              Adds the questions in a file a teammate exported.
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
