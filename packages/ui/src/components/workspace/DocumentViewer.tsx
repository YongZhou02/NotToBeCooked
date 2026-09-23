import React, { useCallback, useState } from "react"
import { AlertCircle, Clock3, LoaderCircle } from "lucide-react"
import { api } from "@workspace/contracts"
import type { MockDocumentFile } from "../../types/course"
import type { Tab } from "../../store/workspace"
import type { CitationItem } from "../chat/Chat"
import { useFileContent } from "../../hooks/useFileContent"
import { DocumentContentState } from "./DocumentContentState"

export interface DocumentViewerProps {
  document: MockDocumentFile
  tab: Tab
  isVisible: boolean
  onPageChange: (page: number) => void
  onZoomChange: (zoom: number) => void
  selectedCitation: CitationItem | null
  onDismissCitation: () => void
  onRetryContent?: (fileId: string) => void
}

export const DocumentViewer: React.FC<DocumentViewerProps> = React.memo(
  ({
    document,
    tab,
    isVisible,
    onPageChange,
    onZoomChange,
    selectedCitation,
    onDismissCitation,
    onRetryContent,
  }) => {
    const [isDownloading, setIsDownloading] = useState(false)
    const [downloadError, setDownloadError] = useState<string | null>(null)
    const page = tab.page ?? 1
    const zoomLevel = tab.zoomLevel ?? 100
    const previewState = document.previewState ?? "ready"
    const {
      state: contentState,
      url: contentUrl,
      retry: retryContent,
    } = useFileContent(document.id, isVisible && previewState !== "unsupported")

    const isCitationOnCurrentPage =
      selectedCitation &&
      selectedCitation.f === document.id &&
      (selectedCitation.p === page || !selectedCitation.p)

    const downloadOriginal = useCallback(async () => {
      setIsDownloading(true)
      setDownloadError(null)

      try {
        const blob = await api.files.content(document.id)
        const url = URL.createObjectURL(blob)
        const anchor = window.document.createElement("a")
        anchor.href = url
        anchor.download = document.name
        window.document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        URL.revokeObjectURL(url)
      } catch (error) {
        setDownloadError(
          error instanceof Error && error.message.trim()
            ? error.message
            : "Couldn’t download the original file. Try again."
        )
      } finally {
        setIsDownloading(false)
      }
    }, [document.id, document.name])

    return (
      <div
        className={`min-h-0 flex-1 flex-col bg-(--bg-canvas,#161F29) ${
          isVisible ? "flex" : "hidden"
        }`}
        aria-hidden={!isVisible}
      >
        {/* Document Viewer Control Bar */}
        <div className="flex items-center justify-between border-b border-(--line-soft,#1B2530) bg-(--bg-panel,#121A23)/40 px-4 py-2.5 text-xs">
          <div className="flex min-w-0 items-center gap-2.5">
            <span
              className="min-w-0 truncate text-sm font-semibold text-(--tx,#DCE3EA)"
              title={document.name}
            >
              {document.name}
            </span>
            <span className="rounded-md bg-(--bg-raise,#1C2833) px-2 py-0.5 font-mono text-[11px] text-(--tx-faint,#5C6976)">
              {document.size} · {document.totalPages} pages
            </span>
          </div>

          {/* Viewer Controls */}
          <div className="ml-3 flex shrink-0 items-center gap-3">
            <div className="flex items-center gap-1.5 rounded-lg border border-(--line,#25313E) bg-(--bg-raise,#1C2833) px-2.5 py-1 text-xs">
              <button
                type="button"
                aria-label="Previous page"
                disabled={page <= 1}
                onClick={() => onPageChange(Math.max(1, page - 1))}
                className="cursor-pointer text-(--tx-dim,#8B98A7) hover:text-white disabled:opacity-40"
              >
                ◀
              </button>
              <span className="px-1.5 font-mono text-xs">
                Page {page} of {document.totalPages}
              </span>
              <button
                type="button"
                aria-label="Next page"
                disabled={page >= document.totalPages}
                onClick={() =>
                  onPageChange(Math.min(document.totalPages, page + 1))
                }
                className="cursor-pointer text-(--tx-dim,#8B98A7) hover:text-white disabled:opacity-40"
              >
                ▶
              </button>
            </div>

            <div className="flex items-center gap-1.5 rounded-lg border border-(--line,#25313E) bg-(--bg-raise,#1C2833) px-2.5 py-1 text-xs">
              <button
                type="button"
                aria-label="Zoom out"
                onClick={() => onZoomChange(Math.max(50, zoomLevel - 10))}
                className="cursor-pointer text-(--tx-dim,#8B98A7) hover:text-white"
              >
                -
              </button>
              <span className="px-1 font-mono text-xs">{zoomLevel}%</span>
              <button
                type="button"
                aria-label="Zoom in"
                onClick={() => onZoomChange(Math.min(150, zoomLevel + 10))}
                className="cursor-pointer text-(--tx-dim,#8B98A7) hover:text-white"
              >
                +
              </button>
            </div>
          </div>
        </div>

        {/* Document Canvas Content Area */}
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-(--bg-canvas,#161F29) p-6 md:p-8 lg:p-10">
          {previewState === "unsupported" ? (
            <DocumentContentState
              variant="unsupported"
              fileName={document.name}
              isDownloading={isDownloading}
              downloadError={downloadError}
              onDownload={() => void downloadOriginal()}
            />
          ) : contentState.status === "idle" ||
            contentState.status === "loading" ? (
            <DocumentContentState variant="loading" fileName={document.name} />
          ) : contentState.status === "error" ? (
            <DocumentContentState
              variant="error"
              fileName={document.name}
              message={contentState.message}
              onRetry={() => {
                retryContent()
                onRetryContent?.(document.id)
              }}
            />
          ) : (
            <>
              {document.status === "uploaded" && (
                <div
                  role="status"
                  className="mb-4 flex items-start gap-2 rounded-sm border border-(--line,#25313E) bg-(--bg-raise,#1C2833)/70 px-3 py-2.5 text-xs text-(--tx-dim,#8B98A7)"
                >
                  <Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-(--acc,#52A8EA)" />
                  <div>
                    <p className="font-semibold text-(--tx,#DCE3EA)">
                      Waiting for AI indexing
                    </p>
                    <p className="mt-0.5">
                      The original file is available. AI search and chat will
                      include it after indexing starts.
                    </p>
                  </div>
                </div>
              )}

              {document.status === "processing" && (
                <div
                  role="status"
                  className="mb-4 flex items-start gap-2 rounded-sm border border-(--acc,#52A8EA)/25 bg-(--acc,#52A8EA)/8 px-3 py-2.5 text-xs text-(--tx-dim,#8B98A7)"
                >
                  <LoaderCircle className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-(--acc,#52A8EA)" />
                  <div>
                    <p className="font-semibold text-(--tx,#DCE3EA)">
                      AI indexing in progress
                    </p>
                    <p className="mt-0.5">
                      You can keep reading. AI search and chat will use this
                      file when indexing finishes.
                    </p>
                  </div>
                </div>
              )}

              {document.status === "failed" && (
                <div
                  role="alert"
                  className="mb-4 flex items-start gap-2 rounded-sm border border-(--danger,#E0625C)/30 bg-(--danger,#E0625C)/10 px-3 py-2.5 text-xs text-(--tx-dim,#8B98A7)"
                >
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-(--danger-tx,#F0A19D)" />
                  <div>
                    <p className="font-semibold text-(--danger-tx,#F0A19D)">
                      AI indexing failed
                    </p>
                    <p className="mt-0.5">
                      The original file remains readable, but AI search and chat
                      cannot use it yet. Open the file actions menu to review or
                      retry.
                    </p>
                  </div>
                </div>
              )}
              {/* Citation Highlight Banner if active */}
              {isCitationOnCurrentPage && (
                <div className="mb-6 flex w-full animate-in items-center justify-between rounded-lg border border-(--cite-line,rgba(227,166,63,0.38)) bg-(--cite-bg,rgba(227,166,63,0.09)) p-3.5 text-xs text-(--cite,#E3A63F) fade-in">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-(--cite,#E3A63F)" />
                    <span>
                      <strong>Citation Evidence:</strong> {selectedCitation.l}{" "}
                      (Page {selectedCitation.p})
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={onDismissCitation}
                    aria-label="Dismiss citation evidence"
                    className="cursor-pointer text-xs hover:text-white"
                  >
                    Dismiss ✕
                  </button>
                </div>
              )}

              {selectedCitation?.quote && isCitationOnCurrentPage && (
                <div className="mb-4 rounded-lg border border-(--cite-line,rgba(227,166,63,0.4)) bg-(--cite-bg,rgba(227,166,63,0.12)) p-4 text-xs leading-relaxed text-(--tx-strong,#EDF2F6) shadow-sm">
                  <span className="mb-1.5 block font-mono text-[11px] font-semibold text-(--cite,#E3A63F) uppercase">
                    Verified Grounded Quote
                  </span>
                  <em>"{selectedCitation.quote}"</em>
                </div>
              )}

              <iframe
                key={`${contentUrl}:${page}:${zoomLevel}`}
                src={`${contentUrl}#page=${page}&zoom=${zoomLevel}`}
                title={document.name}
                className="min-h-[32rem] w-full flex-1 rounded-sm border border-(--line,#25313E) bg-white"
              />
            </>
          )}
        </div>
      </div>
    )
  }
)

DocumentViewer.displayName = "DocumentViewer"
