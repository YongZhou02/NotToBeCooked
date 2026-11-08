import { useMemo, useState } from "react"
import type { CSSProperties, ReactNode } from "react"

import { Button } from "@workspace/ui/components/button"
import { cn } from "@workspace/ui/lib/utils"
import type { SourceDocument } from "@/lib/documents"
import { methodLabel, runShort } from "@/lib/format"
import {
  ALL,
  COLUMNS,
  SCALE,
  buildRows,
  entriesForRun,
  filterEntries,
  formatScore,
  scoreColors,
  sortRows,
  summaryRow,
  tagValues,
  type Cell,
  type GroupBy,
  type MatrixColumn,
  type MatrixFilters,
  type MatrixRow,
  type MethodId,
} from "@/lib/results"
import type { DashboardData } from "@/types"
import { Chip, Eyebrow, HelpButton } from "./bits"

const GROUP_BY: [GroupBy, string][] = [
  ["question", "Each question"],
  ["split", "Split"],
  ["category", "Category"],
  ["origin", "Origin"],
  ["source", "Source PDF"],
  ["answerable", "Answerable"],
  ["outcome", "Answer outcome"],
]

const METHODS: MethodId[] = ["hybrid_rrf", "vector", "keyword"]

function Select({
  label,
  value,
  onChange,
  children,
  wide = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  children: ReactNode
  wide?: boolean
}) {
  return (
    <label className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "h-7 rounded-md border border-input bg-background px-1.5 text-xs",
          wide ? "max-w-none" : "max-w-48"
        )}
      >
        {children}
      </select>
    </label>
  )
}

interface Hover {
  row: MatrixRow
  column: MatrixColumn
  cell: Cell
  rect: DOMRect
}

export function ResultsTab({
  data,
  registry,
  runId,
  onSelectRun,
  onOpenQuestion,
}: {
  data: DashboardData
  registry: readonly SourceDocument[]
  runId: string
  onSelectRun: (id: string) => void
  onOpenQuestion: (id: string) => void
}) {
  const [groupBy, setGroupBy] = useState<GroupBy>("question")
  const [method, setMethod] = useState<MethodId>("hybrid_rrf")
  const [filters, setFilters] = useState<MatrixFilters>(ALL)
  const [sort, setSort] = useState<{
    column: string | null
    direction: "asc" | "desc"
  }>({
    column: null,
    direction: "asc",
  })
  const [hover, setHover] = useState<Hover | null>(null)

  const run = data.runs.find((r) => r.id === runId) ?? data.runs[0]
  const scoredRuns = data.runs.filter((r) =>
    data.questions.some((q) => q.traces?.[r.id]?.scores?.in_run)
  )

  const entries = useMemo(
    () => entriesForRun(data.questions, run.id, registry),
    [data.questions, run.id, registry]
  )
  const shown = useMemo(
    () => filterEntries(entries, filters),
    [entries, filters]
  )

  const sourceLabel = (id: string) =>
    registry.find((d) => d.id === id)?.label ?? id
  const labelFor = (key: Exclude<GroupBy, "question">, value: string) =>
    key === "source" ? sourceLabel(value) : value

  const rows = useMemo(() => {
    const built = buildRows(shown, groupBy, method, (key, value) =>
      key === "source"
        ? (registry.find((d) => d.id === value)?.label ?? value)
        : value
    )
    return sortRows(built, sort.column, sort.direction)
  }, [shown, groupBy, method, sort, registry])
  const total = useMemo(() => summaryRow(shown, method), [shown, method])

  const set = <K extends keyof MatrixFilters>(key: K, value: string) =>
    setFilters((f) => ({ ...f, [key]: value }))
  const filtered = JSON.stringify(filters) !== JSON.stringify(ALL)

  const toggleSort = (column: string) =>
    setSort((s) =>
      s.column !== column
        ? { column, direction: "asc" }
        : s.direction === "asc"
          ? { column, direction: "desc" }
          : { column: null, direction: "asc" }
    )

  const groups = COLUMNS.reduce<{ name: string; span: number }[]>((acc, c) => {
    const last = acc[acc.length - 1]
    if (last && last.name === c.group) last.span++
    else acc.push({ name: c.group, span: 1 })
    return acc
  }, [])

  const groupTitle = (name: string) =>
    name === "Retrieval" ? `Retrieval · ${methodLabel(method)}` : name

  return (
    <div className="mx-auto grid w-full max-w-400 grid-cols-[minmax(0,1fr)] gap-3 p-4">
      <section className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <Eyebrow>Results</Eyebrow>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold tracking-tight">
              Results matrix
            </h2>
            <HelpButton
              label="What the columns mean"
              align="start"
              lines={[
                "Every score is on a 0 to 1 scale. Group rows show the mean.",
                ...COLUMNS.map((c) => `${c.label}: ${c.help}`),
                "A striped cell was not measured for that question (for example, an unanswerable question has no evidence to retrieve). It is left out of every mean, never counted as 0.",
              ]}
            />
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          Run {runShort(run.id)} · {entries.length} questions scored
          {run.generation_model ? ` · answers by ${run.generation_model}` : ""}
          {run.judge?.model ? ` · judged by ${run.judge.model}` : ""}
        </p>
      </section>

      <section
        aria-label="Matrix controls"
        className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-(--line) bg-(--bg-canvas) px-3 py-2"
      >
        <Select label="Run" value={run.id} onChange={onSelectRun} wide>
          {scoredRuns.map((r) => (
            <option key={r.id} value={r.id}>
              {runShort(r.id)} · {r.mode}
            </option>
          ))}
        </Select>
        <Select
          label="Rows"
          value={groupBy}
          onChange={(v) => setGroupBy(v as GroupBy)}
        >
          {GROUP_BY.map(([value, text]) => (
            <option key={value} value={value}>
              {text}
            </option>
          ))}
        </Select>
        <Select
          label="Retrieval"
          value={method}
          onChange={(v) => setMethod(v as MethodId)}
        >
          {METHODS.map((m) => (
            <option key={m} value={m}>
              {methodLabel(m)}
            </option>
          ))}
        </Select>

        <span aria-hidden className="h-5 w-px bg-(--line)" />

        <Select
          label="Split"
          value={filters.split}
          onChange={(v) => set("split", v)}
        >
          <option value="all">All</option>
          {tagValues(entries, "split").map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </Select>
        <Select
          label="Category"
          value={filters.category}
          onChange={(v) => set("category", v)}
        >
          <option value="all">All</option>
          {tagValues(entries, "category").map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </Select>
        <Select
          label="Origin"
          value={filters.origin}
          onChange={(v) => set("origin", v)}
        >
          <option value="all">All</option>
          {tagValues(entries, "origin").map((v) => (
            <option key={v} value={v}>
              {v === "synthetic"
                ? "AI-written"
                : v === "human"
                  ? "Human-written"
                  : v}
            </option>
          ))}
        </Select>
        <Select
          label="Source"
          value={filters.source}
          onChange={(v) => set("source", v)}
        >
          <option value="all">All</option>
          {tagValues(entries, "source")
            .filter((v) => v !== "(no evidence)")
            .map((v) => (
              <option key={v} value={v}>
                {sourceLabel(v)}
              </option>
            ))}
        </Select>
        <Select
          label="Answerable"
          value={filters.answerable}
          onChange={(v) => set("answerable", v)}
        >
          <option value="all">All</option>
          <option value="true">Answerable</option>
          <option value="false">Unanswerable</option>
        </Select>
        <Select
          label="Outcome"
          value={filters.outcome}
          onChange={(v) => set("outcome", v)}
        >
          <option value="all">All</option>
          <option value="shown">Shown</option>
          <option value="blocked">Blocked</option>
          <option value="failed">Model call failed</option>
        </Select>
        <Button
          type="button"
          variant="ghost"
          size="xs"
          disabled={!filtered}
          onClick={() => setFilters(ALL)}
        >
          Clear
        </Button>
        <Chip className="ml-auto">
          {shown.length} of {entries.length} questions
        </Chip>
      </section>

      <Legend />

      {shown.length === 0 ? (
        <p className="rounded-lg border border-dashed border-(--line) p-6 text-center text-sm text-muted-foreground">
          No questions match these filters.
        </p>
      ) : (
        <div
          className="max-h-[calc(100dvh-15rem)] min-h-64 overflow-auto rounded-lg border border-(--line) bg-(--bg-canvas)"
          onScroll={() => setHover(null)}
        >
          <table className="w-max min-w-full border-separate border-spacing-0 text-xs">
            <thead className="sticky top-0 z-20 bg-(--bg-canvas)">
              <tr>
                <th
                  rowSpan={2}
                  scope="col"
                  className="sticky left-0 z-30 min-w-[16rem] border-b border-(--line) bg-(--bg-canvas) px-3 py-1.5 text-left align-bottom font-semibold"
                >
                  {GROUP_BY.find(([g]) => g === groupBy)?.[1]}
                </th>
                <th
                  rowSpan={2}
                  scope="col"
                  title="Questions in this row"
                  className="border-b border-(--line) px-2 py-1.5 text-right align-bottom font-semibold text-muted-foreground"
                >
                  n
                </th>
                {groups.map((g) => (
                  <th
                    key={g.name}
                    colSpan={g.span}
                    scope="colgroup"
                    className="border-b border-l border-(--line) px-2 py-1 text-left text-[11px] font-semibold tracking-wide text-(--tx-dim) uppercase"
                  >
                    {groupTitle(g.name)}
                    {g.name === "AI judge" && (
                      <span className="ml-1 font-normal tracking-normal normal-case">
                        (not yet checked by a human)
                      </span>
                    )}
                  </th>
                ))}
              </tr>
              <tr>
                {COLUMNS.map((c, i) => {
                  const active = sort.column === c.id
                  const firstOfGroup =
                    i === 0 || COLUMNS[i - 1].group !== c.group
                  return (
                    <th
                      key={c.id}
                      scope="col"
                      aria-sort={
                        active
                          ? sort.direction === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                      className={cn(
                        "border-b border-(--line) px-1 py-1 text-center font-medium",
                        firstOfGroup && "border-l"
                      )}
                    >
                      <button
                        type="button"
                        title={`${c.help} Click to sort.`}
                        onClick={() => toggleSort(c.id)}
                        className="w-full min-w-18 rounded px-1 py-0.5 whitespace-nowrap hover:bg-(--bg-hover)"
                      >
                        {c.label}
                        <span
                          aria-hidden
                          className="ml-0.5 inline-block w-2 text-(--tx-dim)"
                        >
                          {active ? (sort.direction === "asc" ? "↑" : "↓") : ""}
                        </span>
                      </button>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody onMouseLeave={() => setHover(null)}>
              <MatrixRowView
                row={total}
                summary
                onHover={setHover}
                onOpenQuestion={onOpenQuestion}
              />
              {rows.map((row) => (
                <MatrixRowView
                  key={row.key}
                  row={row}
                  onHover={setHover}
                  onOpenQuestion={onOpenQuestion}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hover && (
        <CellTooltip
          hover={hover}
          runId={run.id}
          method={method}
          labelFor={labelFor}
          groupBy={groupBy}
        />
      )}
    </div>
  )
}

function MatrixRowView({
  row,
  summary = false,
  onHover,
  onOpenQuestion,
}: {
  row: MatrixRow
  summary?: boolean
  onHover: (hover: Hover | null) => void
  onOpenQuestion: (id: string) => void
}) {
  const q = row.question
  return (
    <tr className={cn(summary && "font-semibold")}>
      <th
        scope="row"
        className={cn(
          "sticky left-0 z-10 max-w-88 min-w-[16rem] border-b border-(--line) bg-(--bg-canvas) px-3 py-1 text-left font-normal",
          summary && "bg-(--bg-raise) font-semibold"
        )}
      >
        {q && row.questionId ? (
          <button
            type="button"
            title="Open this question beside its PDF"
            onClick={() => onOpenQuestion(row.questionId!)}
            className="flex w-full min-w-0 items-center gap-1.5 rounded text-left hover:text-(--acc)"
          >
            <span className="flex-none rounded border border-(--line) px-1 font-mono text-[11px] text-muted-foreground">
              {q.id}
            </span>
            <span className="min-w-0 truncate">{q.question}</span>
          </button>
        ) : (
          <span className="block truncate">{row.label}</span>
        )}
      </th>
      <td
        className={cn(
          "border-b border-(--line) px-2 text-right text-muted-foreground tabular-nums",
          summary && "bg-(--bg-raise)"
        )}
      >
        {row.count}
      </td>
      {COLUMNS.map((c, i) => {
        const cell = row.cells[c.id]
        const firstOfGroup = i === 0 || COLUMNS[i - 1].group !== c.group
        const style: CSSProperties =
          cell.value == null
            ? {
                backgroundImage:
                  "repeating-linear-gradient(135deg, transparent 0 4px, var(--line) 4px 5px)",
              }
            : scoreColors(cell.value)
        return (
          <td
            key={c.id}
            style={style}
            onMouseEnter={(e) =>
              onHover({
                row,
                column: c,
                cell,
                rect: e.currentTarget.getBoundingClientRect(),
              })
            }
            className={cn(
              "border-b border-(--bg-canvas) px-1 py-1 text-center tabular-nums",
              firstOfGroup && "border-l-2 border-l-(--bg-canvas)",
              cell.value == null && "text-muted-foreground"
            )}
          >
            {formatScore(cell.value)}
          </td>
        )
      })}
    </tr>
  )
}

function CellTooltip({
  hover,
  runId,
  method,
  groupBy,
  labelFor,
}: {
  hover: Hover
  runId: string
  method: MethodId
  groupBy: GroupBy
  labelFor: (key: Exclude<GroupBy, "question">, value: string) => string
}) {
  const { row, column, cell, rect } = hover
  const scores = row.question?.traces?.[runId]?.scores
  const left = Math.min(
    Math.max(rect.left + rect.width / 2, 150),
    window.innerWidth - 150
  )
  const below = rect.bottom + 160 < window.innerHeight
  const title =
    row.questionId ??
    (groupBy === "question"
      ? row.label
      : labelFor(groupBy as Exclude<GroupBy, "question">, row.key))

  return (
    <div
      role="tooltip"
      style={{
        position: "fixed",
        left,
        top: below ? rect.bottom + 6 : rect.top - 6,
        transform: `translate(-50%, ${below ? "0" : "-100%"})`,
      }}
      className="pointer-events-none z-50 w-72 rounded-md border border-(--line) bg-popover p-2.5 text-xs leading-snug text-popover-foreground shadow-lg"
    >
      <p className="font-semibold">
        {column.group === "Retrieval"
          ? `${column.label} · ${methodLabel(method)}`
          : column.label}
        <span className="float-right tabular-nums">
          {formatScore(cell.value)}
        </span>
      </p>
      <p className="truncate text-muted-foreground">
        {row.key === "__all" ? "All rows shown" : title}
      </p>
      <p className="mt-1 text-muted-foreground">{column.help}</p>
      <p className="mt-1">
        {cell.value == null
          ? "Not measured for this row."
          : cell.total > 1
            ? `Mean of ${cell.measured} measured question${cell.measured === 1 ? "" : "s"}${
                cell.measured < cell.total
                  ? ` (${cell.total - cell.measured} not measured, left out)`
                  : ""
              }.`
            : ""}
      </p>
      {scores && column.id === "shown" && scores.answer_state !== "shown" && (
        <p className="mt-1">
          {scores.answer_state === "failed"
            ? "The model call failed, so no draft exists."
            : `Blocked: ${(scores.grounding_problems ?? []).join("; ") || "no reason recorded"}`}
        </p>
      )}
      {scores?.judge?.note && column.group === "AI judge" && (
        <p className="mt-1 italic">Judge: {scores.judge.note}</p>
      )}
    </div>
  )
}

function Legend() {
  const stops = [0, 0.25, 0.5, 0.75, 1]
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <div className="flex items-center gap-2">
        <span>0 (worst)</span>
        <span
          aria-hidden
          className="h-3 w-40 rounded-sm"
          style={{
            background: `linear-gradient(to right, ${stops
              .map((s) => scoreColors(s).background)
              .join(", ")})`,
          }}
        />
        <span>1 (best)</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span
          aria-hidden
          className="inline-block size-3 rounded-sm border border-(--line)"
          style={{
            backgroundImage:
              "repeating-linear-gradient(135deg, transparent 0 3px, var(--line) 3px 4px)",
          }}
        />
        <span>not measured (left out of means)</span>
      </div>
      <span title={`Scale ${SCALE.low} → ${SCALE.mid} → ${SCALE.high}`}>
        Red → grey → teal, readable with red-green colour blindness. Every cell
        shows its number.
      </span>
    </div>
  )
}
