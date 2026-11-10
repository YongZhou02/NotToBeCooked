import React from "react"
import { MarkdownContent } from "./MarkdownContent"
import {
  FileText,
  Folder,
  Check,
  RotateCcw,
  Search,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react"

import { type CitationItem, groupCitations } from "../../lib/citations.ts"

export { type CitationItem, groupCitations }

export type FeedbackReason =
  | "answer_incorrect"
  | "retrieval_missed"
  | "citation_unsupported"
  | "answer_incomplete"
  | "document_missing_answer"

export interface AnswerFeedback {
  rating: "positive" | "negative"
  reason?: FeedbackReason | null
  comment?: string | null
}

export interface ChatMessage {
  id?: string
  role?: "user" | "assistant"
  r?: "ai" | "me" // legacy compatibility
  content?: string
  x?: string // legacy compatibility
  cites?: CitationItem[]
  citations?: CitationItem[]
  grounded?: boolean
  /** Files the turn's request named; null or empty means the whole course. */
  mentionedFileIds?: string[] | null
  /** "Searched only X.pdf" -- set on assistant turns (US-12). */
  scopeLabel?: string
  isOptimistic?: boolean
  status?: "pending" | "sent" | "error"
  feedback?: AnswerFeedback | null
  createdAt?: string | Date
}

export interface ChatMessageProps {
  message: ChatMessage
  onCiteClick?: (cite: CitationItem) => void
  /** Shown as "Ask again" under the answer when set (US-11). */
  onRetry?: () => void
  onFeedback?: (
    messageId: string,
    rating: "positive" | "negative",
    reason?: FeedbackReason | null,
    comment?: string | null
  ) => Promise<void> | void
  className?: string
}

export function renderMentionized(text: string): React.ReactNode {
  // Matches confirmed atomic mentions @[Filename or Category] OR standard @word
  const parts = text.split(/(@\[[^\]]+\]|@[^\s]+)/g)
  return parts.map((part, i) => {
    if (part.startsWith("@[") && part.endsWith("]")) {
      const label = part.slice(2, -1)
      const isPdf =
        label.toLowerCase().endsWith(".pdf") ||
        label.toLowerCase().includes("doc") ||
        label.toLowerCase().includes("pdf")
      return (
        <span
          key={i}
          className="mx-0.5 inline-flex items-center gap-1 font-medium text-(--acc,#52A8EA) select-none"
        >
          {isPdf ? (
            <FileText className="inline-block h-3.5 w-3.5 shrink-0 align-sub text-(--acc,#52A8EA)" />
          ) : (
            <Folder className="inline-block h-3.5 w-3.5 shrink-0 align-sub text-(--acc,#52A8EA)" />
          )}
          <span>{label}</span>
        </span>
      )
    } else if (part.startsWith("@")) {
      const label = part.slice(1)
      return (
        <span
          key={i}
          className="mx-0.5 inline-flex items-center gap-1 font-medium text-(--acc,#52A8EA) select-none"
        >
          <FileText className="inline-block h-3.5 w-3.5 shrink-0 align-sub text-(--acc,#52A8EA)" />
          <span>{label}</span>
        </span>
      )
    }
    return part
  })
}

export const ChatMessageItem: React.FC<ChatMessageProps> = ({
  message,
  onCiteClick,
  onRetry,
  onFeedback,
  className = "",
}) => {
  const isMe = message.role === "user" || message.r === "me"
  const rawText = message.content ?? message.x ?? ""
  const citations = message.citations ?? message.cites ?? []
  const isOptimistic = message.isOptimistic || message.status === "pending"
  const [feedbackOpen, setFeedbackOpen] = React.useState(false)
  const [reason, setReason] = React.useState<FeedbackReason>(
    message.feedback?.reason ?? "answer_incorrect"
  )
  const [comment, setComment] = React.useState(message.feedback?.comment ?? "")
  const [feedbackError, setFeedbackError] = React.useState<string | null>(null)
  const [isSubmittingFeedback, setIsSubmittingFeedback] = React.useState(false)

  const submitFeedback = async (
    rating: "positive" | "negative",
    selectedReason?: FeedbackReason | null,
    feedbackComment?: string | null
  ) => {
    if (!message.id || !onFeedback) return
    setFeedbackError(null)
    setIsSubmittingFeedback(true)
    try {
      await onFeedback(message.id, rating, selectedReason, feedbackComment)
      setFeedbackOpen(false)
    } catch {
      setFeedbackError("Could not save feedback. Please try again.")
    } finally {
      setIsSubmittingFeedback(false)
    }
  }

  return (
    <div
      className={`flex flex-col gap-0.5 ${
        isMe ? "items-end" : "w-full items-start"
      } ${className}`}
    >
      {/* User Bubble or Assistant Full-width Text */}
      <div
        className={`text-[13.5px] leading-relaxed select-text ${
          isMe
            ? "max-w-[85%] rounded-lg rounded-tr-xs border border-[rgba(var(--acc-rgb,82,168,234),0.25)] bg-[rgba(var(--acc-rgb,82,168,234),0.12)] px-3 py-2 text-(--acc-tx-soft,#A8D4F2)"
            : "w-full py-0.5 text-justify text-(--tx,#DCE3EA)"
        } ${isOptimistic ? "animate-pulse opacity-70" : ""}`}
      >
        {isMe ? (
          <div className="whitespace-pre-wrap select-text">
            {renderMentionized(rawText)}
          </div>
        ) : (
          <MarkdownContent
            content={rawText}
            citations={citations}
            onCiteClick={onCiteClick}
            className="select-text"
          />
        )}

        {/* Citations List (One pill per source marker) */}
        {citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 border-t border-(--line-soft,#1B2530)/60 pt-1">
            {citations.map((cite, cIdx) => (
              <button
                key={cite.marker ?? cIdx}
                type="button"
                onClick={() => onCiteClick?.(cite)}
                className="inline-flex cursor-pointer items-center gap-1.5 rounded border border-(--cite-line,rgba(227,166,63,0.38)) bg-(--cite-bg,rgba(227,166,63,0.09)) px-2 py-0.5 font-mono text-[10.5px] text-(--cite,#E3A63F) [outline:none] transition-colors outline-none hover:bg-[rgba(227,166,63,0.19)] focus:ring-0 focus:outline-none focus-visible:ring-0 focus-visible:outline-none"
              >
                <Check className="h-2.5 w-2.5" />
                <span>
                  {cite.marker ? `[${cite.marker}] ` : ""}
                  {cite.l}
                  {cite.quotes && cite.quotes.length > 1
                    ? ` (${cite.quotes.length})`
                    : ""}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {!isMe && (message.scopeLabel || onRetry) && (
        <div className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 pt-0.5 text-[10.5px] text-(--tx-faint,#5C6976)">
          {message.scopeLabel && (
            <span className="inline-flex min-w-0 items-center gap-1">
              <Search className="h-2.5 w-2.5 shrink-0" />
              <span className="truncate">{message.scopeLabel}</span>
            </span>
          )}
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex cursor-pointer items-center gap-1 rounded px-1 py-0.5 font-medium text-(--acc,#52A8EA) hover:bg-(--bg-hover,#213040)"
            >
              <RotateCcw className="h-2.5 w-2.5" />
              Ask again
            </button>
          )}
        </div>
      )}

      {!isMe && message.id && !isOptimistic && onFeedback && (
        <div className="w-full pt-1">
          <div className="flex items-center gap-1 text-(--tx-faint,#5C6976)">
            <span className="mr-1 text-[10.5px]">Was this helpful?</span>
            <button
              type="button"
              aria-label="Mark answer as helpful"
              aria-pressed={message.feedback?.rating === "positive"}
              disabled={isSubmittingFeedback}
              onClick={() => void submitFeedback("positive", null, null)}
              className={`rounded p-1 transition-colors hover:bg-(--bg-hover,#213040) hover:text-green-400 disabled:opacity-50 ${
                message.feedback?.rating === "positive" ? "text-green-400" : ""
              }`}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              aria-label="Mark answer as unhelpful"
              aria-pressed={message.feedback?.rating === "negative"}
              disabled={isSubmittingFeedback}
              onClick={() => setFeedbackOpen((open) => !open)}
              className={`rounded p-1 transition-colors hover:bg-(--bg-hover,#213040) hover:text-red-400 disabled:opacity-50 ${
                message.feedback?.rating === "negative" ? "text-red-400" : ""
              }`}
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </button>
          </div>

          {feedbackOpen && (
            <div className="mt-1.5 space-y-2 rounded-md border border-(--line,#25313E) bg-(--bg-raise,#1C2833) p-2 text-[11px]">
              <label className="block space-y-1">
                <span className="text-(--tx-dim,#8B98A7)">
                  What went wrong?
                </span>
                <select
                  value={reason}
                  onChange={(event) =>
                    setReason(event.target.value as FeedbackReason)
                  }
                  className="w-full rounded border border-(--line,#25313E) bg-(--bg-panel,#121A23) px-2 py-1.5 text-(--tx,#DCE3EA) outline-none focus:border-(--acc,#52A8EA)"
                >
                  <option value="answer_incorrect">Answer is incorrect</option>
                  <option value="retrieval_missed">
                    Relevant information was not retrieved
                  </option>
                  <option value="citation_unsupported">
                    Citation does not support the answer
                  </option>
                  <option value="answer_incomplete">
                    Answer is incomplete
                  </option>
                  <option value="document_missing_answer">
                    Document does not contain the answer
                  </option>
                </select>
              </label>

              <label className="block space-y-1">
                <span className="text-(--tx-dim,#8B98A7)">
                  Comment (optional)
                </span>
                <textarea
                  value={comment}
                  maxLength={1000}
                  rows={2}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder="Tell us what you expected."
                  className="w-full resize-y rounded border border-(--line,#25313E) bg-(--bg-panel,#121A23) px-2 py-1.5 text-(--tx,#DCE3EA) outline-none placeholder:text-(--tx-faint,#5C6976) focus:border-(--acc,#52A8EA)"
                />
              </label>

              {feedbackError && <p className="text-red-400">{feedbackError}</p>}

              <div className="flex justify-end gap-1.5">
                <button
                  type="button"
                  disabled={isSubmittingFeedback}
                  onClick={() => setFeedbackOpen(false)}
                  className="rounded px-2 py-1 text-(--tx-dim,#8B98A7) hover:bg-(--bg-hover,#213040) disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={isSubmittingFeedback}
                  onClick={() =>
                    void submitFeedback("negative", reason, comment || null)
                  }
                  className="rounded bg-(--acc,#52A8EA) px-2 py-1 font-medium text-white hover:opacity-90 disabled:opacity-50"
                >
                  {isSubmittingFeedback ? "Saving..." : "Submit"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ChatMessageItem
