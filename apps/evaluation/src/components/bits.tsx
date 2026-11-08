import { useEffect, useId, useLayoutEffect, useRef, useState } from "react"
import type { ReactNode } from "react"

import { Badge } from "@workspace/ui/components/badge"
import { cn } from "@workspace/ui/lib/utils"

/** A question-mark button with a short explanation, on hover, focus or tap. */
export function HelpButton({
  label,
  lines,
  align = "end",
}: {
  label: string
  lines: string[]
  /** Which edge of the button the explanation lines up with. */
  align?: "start" | "end"
}) {
  const id = useId()
  const [hover, setHover] = useState(false)
  const [focus, setFocus] = useState(false)
  const [pinned, setPinned] = useState(false)
  const tip = useRef<HTMLSpanElement>(null)
  const shown = hover || focus || pinned

  // Keep the explanation inside the window, wherever the button is.
  useLayoutEffect(() => {
    const el = tip.current
    if (!shown || !el) return
    el.style.translate = "0 0"
    const rect = el.getBoundingClientRect()
    const margin = 8
    let shift = 0
    if (rect.left < margin) shift = margin - rect.left
    else if (rect.right > window.innerWidth - margin)
      shift = window.innerWidth - margin - rect.right
    el.style.translate = `${shift}px 0`
  }, [shown])

  useEffect(() => {
    if (!pinned) return
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPinned(false)
    }
    document.addEventListener("keydown", close)
    return () => document.removeEventListener("keydown", close)
  }, [pinned])

  const [first, ...rest] = lines
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <button
        type="button"
        aria-label={label}
        aria-describedby={shown ? id : undefined}
        aria-expanded={shown}
        onClick={() => setPinned((p) => !p)}
        onFocus={() => setFocus(true)}
        onBlur={() => {
          setFocus(false)
          setPinned(false)
        }}
        className="inline-flex size-5 cursor-help items-center justify-center rounded-full border border-(--line) bg-(--bg-raise) text-[11px] font-semibold text-(--tx-dim) transition-colors hover:border-(--acc) hover:text-(--acc) focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        ?
      </button>
      {shown && (
        <span
          ref={tip}
          id={id}
          role="tooltip"
          className={cn(
            "absolute top-full z-30 mt-1.5 w-64 max-w-[calc(100vw-1rem)] rounded-md border border-(--line) bg-popover p-2.5 text-left text-xs leading-snug font-normal text-popover-foreground shadow-lg",
            align === "end" ? "right-0" : "left-0"
          )}
        >
          <strong className="block font-semibold">{first}</strong>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted-foreground">
            {rest.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </span>
      )}
    </span>
  )
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="text-[11px] font-semibold tracking-widest text-(--tx-dim) uppercase">
      {children}
    </p>
  )
}

export function Panel({
  className,
  children,
  ...props
}: React.ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "min-w-0 rounded-xl border border-(--line) bg-(--bg-canvas) p-4",
        className
      )}
      {...props}
    >
      {children}
    </section>
  )
}

export function SectionHead({
  eyebrow,
  title,
  titleId,
  right,
  help,
}: {
  eyebrow: string
  title: string
  titleId?: string
  right?: ReactNode
  help?: ReactNode
}) {
  return (
    <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        <div className="flex items-center gap-2">
          <h2 id={titleId} className="text-lg font-semibold tracking-tight">
            {title}
          </h2>
          {help}
        </div>
      </div>
      {right}
    </div>
  )
}

/** A small status label. */
export function Chip({
  tone = "neutral",
  className,
  children,
  title,
  ...rest
}: {
  tone?: "neutral" | "accent" | "ok" | "warn" | "danger" | "cite"
  className?: string
  children: ReactNode
  title?: string
  "data-testid"?: string
}) {
  const tones = {
    neutral: "bg-secondary text-secondary-foreground",
    accent: "bg-primary/15 text-(--acc-tx-soft)",
    ok: "bg-(--ok)/15 text-(--ok)",
    warn: "bg-(--cite-bg) text-(--cite-tx)",
    danger: "bg-destructive/15 text-(--danger-tx)",
    cite: "bg-(--cite-bg) text-(--cite-tx)",
  } as const
  return (
    <Badge
      variant="secondary"
      title={title}
      className={cn("h-auto py-0.5", tones[tone], className)}
      {...rest}
    >
      {children}
    </Badge>
  )
}

export function ScrollTable({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto">{children}</div>
}
