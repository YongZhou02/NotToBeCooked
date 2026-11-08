import { useEffect, useState } from "react"

import { loadData, type LoadedData } from "@/lib/load-data"
import { buildRegistry } from "@/lib/documents"
import { cn } from "@workspace/ui/lib/utils"

export type TabId = "dashboard" | "runs" | "visualization"

const TABS: { id: TabId; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "runs", label: "Run evaluations" },
  { id: "visualization", label: "Visualization & Annotation" },
]

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; loaded: LoadedData }

export function App() {
  const [load, setLoad] = useState<LoadState>({ status: "loading" })
  const [tab, setTab] = useState<TabId>("dashboard")

  useEffect(() => {
    let cancelled = false
    loadData().then(
      (loaded) => {
        if (!cancelled) setLoad({ status: "ready", loaded })
      },
      (error: unknown) => {
        if (!cancelled)
          setLoad({
            status: "error",
            message: error instanceof Error ? error.message : String(error),
          })
      }
    )
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="flex h-dvh flex-col bg-background font-sans text-foreground">
      <header className="flex flex-none flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-(--line) bg-(--bg-bar) px-4 py-2">
        <div className="flex flex-col leading-tight">
          <span className="text-[11px] font-semibold tracking-widest text-(--tx-dim) uppercase">
            NTBC
          </span>
          <h1 className="text-base font-semibold">Evaluation Hub</h1>
        </div>
        <nav
          role="tablist"
          aria-label="Evaluation sections"
          className="flex max-w-full gap-1 overflow-x-auto"
        >
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={tab === t.id}
              aria-controls={`panel-${t.id}`}
              onClick={() => setTab(t.id)}
              className={cn(
                "relative rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors",
                tab === t.id
                  ? "bg-(--bg-canvas) text-(--tx) before:absolute before:inset-x-2 before:top-0 before:h-0.5 before:rounded before:bg-(--acc)"
                  : "text-(--tx-dim) hover:bg-(--bg-raise) hover:text-(--tx)"
              )}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        {load.status === "loading" && (
          <p className="p-6 text-sm text-muted-foreground">
            Loading the evaluation data...
          </p>
        )}
        {load.status === "error" && (
          <div
            role="alert"
            className="m-6 max-w-xl rounded-lg border p-4 text-sm"
          >
            <p className="font-medium">
              The evaluation data could not be loaded.
            </p>
            <p className="mt-1 text-muted-foreground">{load.message}</p>
            <p className="mt-2 text-muted-foreground">
              Start the app with <code>pnpm dev:evaluation</code> from the
              repository root.
            </p>
          </div>
        )}
        {load.status === "ready" && (
          <p className="p-6 text-sm text-muted-foreground">
            {load.loaded.data.questions.length} questions,{" "}
            {buildRegistry(load.loaded.data, load.loaded.files).length} source
            PDFs loaded.
          </p>
        )}
      </main>
    </div>
  )
}
