import {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react"

import { Button } from "@workspace/ui/components/button"
import { resolveDocument, type SourceDocument } from "@/lib/documents"

// pdf.js and its worker load only when the first page is shown.
const PdfViewer = lazy(
  () => import("@workspace/ui/components/workspace/PdfViewer")
)

/** Which page of which PDF is on screen, and the quote marked on it. */
export interface PdfView {
  docId: string
  page: number
  quote: string
}

const ZOOM_STEP = 15
const ZOOM_MIN = 60
const ZOOM_MAX = 250

/** Scrolls `box` so the elements sit in its middle, touching nothing else. */
function centerInside(
  box: HTMLElement,
  elements: HTMLElement[],
  behavior: ScrollBehavior
) {
  if (elements.length === 0) return
  const frame = box.getBoundingClientRect()
  const rects = elements.map((el) => el.getBoundingClientRect())
  const top = Math.min(...rects.map((r) => r.top))
  const bottom = Math.max(...rects.map((r) => r.bottom))
  const left = Math.min(...rects.map((r) => r.left))
  box.scrollTo({
    top:
      box.scrollTop + top - frame.top - (box.clientHeight - (bottom - top)) / 2,
    left: box.scrollLeft + left - frame.left - 12,
    behavior,
  })
}

export function PdfPane({
  registry,
  view,
  evidence,
  onView,
  paneRef,
}: {
  registry: readonly SourceDocument[]
  view: PdfView | null
  /** The gold quote the reviewer is looking at, if any. */
  evidence: PdfView | null
  onView: (view: PdfView) => void
  /** The scrolling element; the caller reads the text selection from it. */
  paneRef: RefObject<HTMLDivElement | null>
}) {
  const doc = view ? resolveDocument(registry, view.docId) : undefined
  const [zoom, setZoom] = useState(100)
  const [counted, setCounted] = useState<{ url: string; pages: number } | null>(
    null
  )
  const [quoteResult, setQuoteResult] = useState<{
    key: string
    found: boolean
  } | null>(null)

  const total =
    doc && counted?.url === doc.url ? counted.pages : (doc?.pages ?? undefined)
  const page = view ? (total ? Math.min(view.page, total) : view.page) : 1
  const quoteKey = doc && view ? `${doc.url}#${page}#${view.quote}` : ""
  const quoteKeyRef = useRef(quoteKey)
  useEffect(() => {
    quoteKeyRef.current = quoteKey
  }, [quoteKey])

  const quote = view?.quote ?? ""
  const quotes = useMemo(() => (quote.trim() ? [quote] : []), [quote])
  const handleQuoteFound = useCallback((found: boolean) => {
    setQuoteResult({ key: quoteKeyRef.current, found })
  }, [])
  const handleNumPages = useCallback(
    (pages: number) => {
      if (doc) setCounted({ url: doc.url, pages })
    },
    [doc]
  )

  // A new page opens at its top unless a quote on it is about to be centred.
  const docUrl = doc?.url
  useEffect(() => {
    paneRef.current?.scrollTo({ top: 0, left: 0 })
  }, [docUrl, page, paneRef])

  const evidenceDoc = evidence
    ? resolveDocument(registry, evidence.docId)
    : undefined
  const onEvidencePage = Boolean(
    evidence &&
    evidence.quote.trim() &&
    evidenceDoc &&
    doc &&
    evidenceDoc.id === doc.id &&
    evidence.page === page
  )
  const quoteMissing =
    onEvidencePage && quoteResult?.key === quoteKey && !quoteResult.found

  const go = (next: Partial<PdfView>) => {
    if (!view) return
    onView({ ...view, ...next })
  }
  const setPage = (n: number) =>
    go({ page: Math.max(1, Math.min(total ?? n, Math.floor(n) || 1)) })

  const locate = () => {
    if (!evidence || !evidence.quote.trim()) return
    if (!onEvidencePage) {
      onView(evidence)
      return
    }
    const marked = [
      ...(paneRef.current?.querySelectorAll<HTMLElement>(".ntbc-quote") ?? []),
    ]
    if (paneRef.current) centerInside(paneRef.current, marked, "smooth")
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-(--line) bg-(--bg-canvas)">
      <div className="flex flex-none flex-wrap items-center gap-2 border-b border-(--line) bg-(--bg-bar) p-1.5">
        <select
          aria-label="Select source document"
          value={doc?.id ?? ""}
          disabled={registry.length === 0}
          onChange={(e) =>
            onView({ docId: e.target.value, page: 1, quote: "" })
          }
          className="h-8 max-w-[11rem] min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-sm min-[1000px]:flex-none"
        >
          {registry.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            title="Previous page in PDF"
            aria-label="Previous PDF page"
            disabled={!doc || page <= 1}
            onClick={() => setPage(page - 1)}
          >
            ‹
          </Button>
          <label className="flex items-center gap-1 text-sm">
            <input
              type="number"
              min={1}
              max={total}
              value={page}
              aria-label="PDF page number"
              onChange={(e) => {
                const n = parseInt(e.target.value, 10)
                if (n >= 1) setPage(n)
              }}
              className="h-8 w-14 rounded-md border border-input bg-background px-1.5 text-center text-sm"
            />
            <span className="text-muted-foreground">/ {total ?? "…"}</span>
          </label>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            title="Next page in PDF"
            aria-label="Next PDF page"
            disabled={!doc || (total != null && page >= total)}
            onClick={() => setPage(page + 1)}
          >
            ›
          </Button>
        </div>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            title="Zoom out"
            aria-label="Zoom out"
            onClick={() => setZoom((z) => Math.max(ZOOM_MIN, z - ZOOM_STEP))}
          >
            −
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            title="Fit width and reset zoom"
            onClick={() => setZoom(100)}
          >
            {zoom === 100 ? "Fit" : `${zoom}%`}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            title="Zoom in"
            aria-label="Zoom in"
            onClick={() => setZoom((z) => Math.min(ZOOM_MAX, z + ZOOM_STEP))}
          >
            +
          </Button>
        </div>

        <div className="ml-auto flex items-center gap-1">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={!evidence || !evidence.quote.trim()}
            title="Go back to the highlighted gold evidence"
            onClick={locate}
          >
            Locate quote
          </Button>
          {doc && (
            <a
              href={`${doc.url}#page=${page}&view=FitH`}
              target="_blank"
              rel="noreferrer"
              title="Open the PDF in a new tab"
              className="inline-flex h-8 items-center rounded-md px-2.5 text-sm font-medium hover:bg-muted"
            >
              Open ↗
            </a>
          )}
        </div>
      </div>

      <div className="relative min-h-0 flex-1">
        <div
          ref={paneRef}
          data-testid="pdf-scroll"
          className="h-full overflow-auto bg-(--bg-panel) p-2"
        >
          {doc ? (
            <Suspense
              fallback={
                <p className="p-2 text-sm text-muted-foreground">
                  Loading the PDF viewer...
                </p>
              }
            >
              <PdfViewer
                url={doc.url}
                page={page}
                zoom={zoom}
                quotes={quotes}
                onQuoteFound={handleQuoteFound}
                scrollContainerRef={paneRef}
                onNumPages={handleNumPages}
              />
            </Suspense>
          ) : (
            <p className="p-2 text-sm text-muted-foreground">
              No source PDFs were found in the documents folder.
            </p>
          )}
        </div>
        {quoteMissing && (
          <p
            role="status"
            className="pointer-events-none absolute inset-x-2 bottom-2 rounded-md border border-(--cite-line) bg-popover px-2.5 py-1.5 text-sm text-(--cite-tx) shadow"
          >
            Quote not matched in this page&apos;s text
          </p>
        )}
      </div>
    </div>
  )
}
