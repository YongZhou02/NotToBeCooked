import { useCallback, useEffect, useMemo, useState } from "react"

import { loadData, type LoadedData } from "@/lib/load-data"
import { buildRegistry } from "@/lib/documents"
import { computeSplitMetrics, getAllQuestions } from "@/lib/questions"
import { useEvalStore } from "@/lib/use-eval-store"
import { cn } from "@workspace/ui/lib/utils"
import { DashboardTab } from "@/components/DashboardTab"
import { RunsTab } from "@/components/RunsTab"
import { VisualizationTab } from "@/components/VisualizationTab"

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

  if (load.status === "ready") return <Workbench loaded={load.loaded} />

  return (
    <div className="flex h-dvh flex-col bg-background font-sans text-foreground">
      <Header tab="dashboard" onTab={() => undefined} />
      <main className="min-h-0 flex-1 overflow-y-auto">
        {load.status === "loading" ? (
          <p className="p-6 text-sm text-muted-foreground">
            Loading the evaluation data...
          </p>
        ) : (
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
      </main>
    </div>
  )
}

function Header({ tab, onTab }: { tab: TabId; onTab: (tab: TabId) => void }) {
  return (
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
            data-tab={t.id}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            onClick={() => onTab(t.id)}
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
  )
}

/** A request to show one question in the Visualization tab. */
export interface FocusRequest {
  id: string
  nonce: number
}

function Workbench({ loaded }: { loaded: LoadedData }) {
  const { data, files } = loaded
  const store = useEvalStore()
  const registry = useMemo(() => buildRegistry(data, files), [data, files])
  const [tab, setTab] = useState<TabId>("dashboard")
  const [runId, setRunId] = useState(data.selected_run_id)
  const [traceQuestionId, setTraceQuestionId] = useState(
    data.questions[0]?.id ?? ""
  )
  const [focus, setFocus] = useState<FocusRequest | null>(null)

  const run = data.runs.find((r) => r.id === runId) ?? data.runs[0]
  const all = useMemo(
    () => getAllQuestions(store.state, data),
    [store.state, data]
  )
  const metrics = useMemo(() => computeSplitMetrics(all), [all])

  const openQuestion = useCallback((id: string) => {
    setFocus((previous) => ({ id, nonce: (previous?.nonce ?? 0) + 1 }))
    setTab("visualization")
  }, [])

  if (!run)
    return (
      <p className="p-6 text-sm">The data file does not list any runs yet.</p>
    )

  return (
    <div className="flex h-dvh flex-col bg-background font-sans text-foreground">
      <Header tab={tab} onTab={setTab} />
      <main className={cn("min-h-0 flex-1 overflow-y-auto")}>
        <div
          role="tabpanel"
          id="panel-dashboard"
          aria-labelledby="tab-dashboard"
          hidden={tab !== "dashboard"}
          data-panel="dashboard"
        >
          {tab === "dashboard" && (
            <DashboardTab
              data={data}
              run={run}
              metrics={metrics}
              onOpenQuestion={openQuestion}
            />
          )}
        </div>
        <div
          role="tabpanel"
          id="panel-runs"
          aria-labelledby="tab-runs"
          hidden={tab !== "runs"}
          data-panel="runs"
        >
          {tab === "runs" && (
            <RunsTab
              data={data}
              runId={run.id}
              onSelectRun={setRunId}
              traceQuestionId={traceQuestionId}
              onSelectTraceQuestion={setTraceQuestionId}
              metrics={metrics}
              registry={registry}
            />
          )}
        </div>
        <div
          role="tabpanel"
          id="panel-visualization"
          aria-labelledby="tab-visualization"
          hidden={tab !== "visualization"}
          data-panel="visualization"
          className="h-full"
        >
          <VisualizationTab
            data={data}
            registry={registry}
            store={store}
            all={all}
            runId={run.id}
            focus={focus}
            isActive={tab === "visualization"}
          />
        </div>
      </main>
    </div>
  )
}
