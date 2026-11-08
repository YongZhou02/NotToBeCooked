import { Search } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { cn } from "@workspace/ui/lib/utils"
import {
  defaultFilters,
  filtersAreDefault,
  type Filters,
} from "@/lib/questions"
import type { SourceDocument } from "@/lib/documents"
import { Chip } from "./bits"

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: [T, string][]
  onChange: (value: T) => void
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div
        role="group"
        aria-label={`Filter by ${label.toLowerCase()}`}
        className="flex rounded-md border border-(--line) bg-(--bg-raise) p-0.5"
      >
        {options.map(([optionValue, text]) => (
          <button
            key={optionValue}
            type="button"
            aria-pressed={value === optionValue}
            data-value={optionValue}
            onClick={() => onChange(optionValue)}
            className={cn(
              "rounded px-2 py-0.5 text-xs font-medium transition-colors",
              value === optionValue
                ? "bg-primary text-primary-foreground"
                : "text-(--tx-dim) hover:bg-(--bg-hover) hover:text-(--tx)"
            )}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  )
}

function SelectField({
  label,
  value,
  onChange,
  children,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  children: React.ReactNode
}) {
  return (
    <label className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <select
        aria-label={`Filter by ${label.toLowerCase()}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-7 max-w-[11rem] rounded-md border border-input bg-background px-1.5 text-xs"
      >
        {children}
      </select>
    </label>
  )
}

export function FilterBar({
  filters,
  onChange,
  registry,
  sourceCounts,
  totalCount,
  verified,
  reviewed,
  total,
  inert,
}: {
  filters: Filters
  onChange: (next: Filters) => void
  registry: readonly SourceDocument[]
  sourceCounts: ReadonlyMap<string, number>
  totalCount: number
  verified: number
  reviewed: number
  total: number
  inert: boolean
}) {
  const set = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    onChange({ ...filters, [key]: value })

  return (
    <section
      aria-label="Filter questions"
      inert={inert}
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border border-(--line) bg-(--bg-canvas) px-2.5 py-1.5",
        inert && "opacity-45"
      )}
    >
      <div className="relative min-w-[110px] flex-1 basis-[150px]">
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="search"
          id="filterSearch"
          placeholder="Search questions, answers, IDs..."
          aria-label="Search questions"
          value={filters.search}
          onChange={(e) => set("search", e.target.value)}
          className="h-7 pl-7 text-xs md:text-xs"
        />
      </div>

      <Segmented
        label="Author"
        value={filters.origin}
        options={[
          ["all", "All"],
          ["human", "Human"],
          ["synthetic", "AI"],
        ]}
        onChange={(v) => set("origin", v)}
      />

      <SelectField
        label="Source"
        value={filters.source}
        onChange={(v) => set("source", v)}
      >
        <option value="all">All sources ({totalCount})</option>
        {registry.map((doc) => (
          <option key={doc.id} value={doc.id}>
            {doc.label} ({sourceCounts.get(doc.id) ?? 0})
          </option>
        ))}
      </SelectField>

      <Segmented
        label="Answer key"
        value={filters.verification}
        options={[
          ["all", "All"],
          ["unverified", "Unverified"],
          ["verified", "Verified"],
        ]}
        onChange={(v) => set("verification", v)}
      />

      <Segmented
        label="Type"
        value={filters.difficulty}
        options={[
          ["all", "All"],
          ["hard", "Hard"],
        ]}
        onChange={(v) => set("difficulty", v)}
      />

      <SelectField
        label="Split"
        value={filters.split}
        onChange={(v) => set("split", v as Filters["split"])}
      >
        <option value="all">All</option>
        <option value="dev">Dev</option>
        <option value="test">Test</option>
      </SelectField>

      <Button
        type="button"
        id="clearFilters"
        variant="ghost"
        size="xs"
        disabled={filtersAreDefault(filters)}
        onClick={() => onChange(defaultFilters())}
      >
        Clear
      </Button>

      <div className="ml-auto flex items-center gap-1.5">
        <Chip tone="ok" className="tabular-nums">
          {verified} / {total} verified
        </Chip>
        <Chip className="tabular-nums">
          {reviewed} / {total} reviewed
        </Chip>
      </div>
    </section>
  )
}
