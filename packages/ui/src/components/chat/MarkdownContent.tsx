import React from "react"
import type { CitationItem } from "./ChatMessage"
import { FileText, Folder } from "lucide-react"
import { splitInlineTokens } from "../../lib/inlineTokens"

export interface MarkdownContentProps {
  content: string
  citations?: CitationItem[]
  onCiteClick?: (cite: CitationItem) => void
  className?: string
}

function parseInline(
  text: string,
  citations: CitationItem[] = [],
  onCiteClick?: (cite: CitationItem) => void
): React.ReactNode[] {
  // The pattern and what it covers live in lib/inlineTokens.ts, where a test
  // can reach them.
  const tokens = splitInlineTokens(text)

  return tokens.map((token, idx) => {
    if (!token) return null

    // Inline Code (borderless, font sized cleanly and aligned with text)
    if (token.startsWith("`") && token.endsWith("`") && token.length >= 2) {
      return (
        <code
          key={idx}
          className="mx-0.5 inline-block rounded bg-(--bg-raise,#1C2833)/80 px-1 py-0.5 font-mono text-[13px] text-(--acc,#52A8EA) align-baseline leading-none select-text"
        >
          {token.slice(1, -1)}
        </code>
      )
    }

    // Bold + Italic (***text***)
    if (token.startsWith("***") && token.endsWith("***") && token.length >= 6) {
      return (
        <strong key={idx} className="font-bold italic text-(--tx,#DCE3EA)">
          {token.slice(3, -3)}
        </strong>
      )
    }

    // Bold (**text** or __text__)
    if (
      (token.startsWith("**") && token.endsWith("**") && token.length >= 4) ||
      (token.startsWith("__") && token.endsWith("__") && token.length >= 4)
    ) {
      return (
        <strong key={idx} className="font-semibold text-(--tx,#DCE3EA)">
          {token.slice(2, -2)}
        </strong>
      )
    }

    // Italic (*text* or _text_)
    if (
      (token.startsWith("*") && token.endsWith("*") && token.length >= 2) ||
      (token.startsWith("_") && token.endsWith("_") && token.length >= 2)
    ) {
      return (
        <em key={idx} className="italic text-(--tx-dim,#8B98A7)">
          {token.slice(1, -1)}
        </em>
      )
    }

    // Atomic Mention @[Filename]
    if (token.startsWith("@[") && token.endsWith("]")) {
      const label = token.slice(2, -1)
      const isPdf =
        label.toLowerCase().endsWith(".pdf") ||
        label.toLowerCase().includes("doc") ||
        label.toLowerCase().includes("pdf")
      return (
        <span
          key={idx}
          className="mx-0.5 inline-flex items-center gap-1 font-medium text-(--acc,#52A8EA) select-none"
        >
          {isPdf ? (
            <FileText className="inline-block shrink-0 align-sub h-3.5 w-3.5 text-(--acc,#52A8EA)" />
          ) : (
            <Folder className="inline-block shrink-0 align-sub h-3.5 w-3.5 text-(--acc,#52A8EA)" />
          )}
          <span>{label}</span>
        </span>
      )
    }

    // Standard @word Mention
    if (token.startsWith("@")) {
      const label = token.slice(1)
      return (
        <span
          key={idx}
          className="mx-0.5 inline-flex items-center gap-1 font-medium text-(--acc,#52A8EA) select-none"
        >
          <FileText className="inline-block shrink-0 align-sub h-3.5 w-3.5 text-(--acc,#52A8EA)" />
          <span>{label}</span>
        </span>
      )
    }

    // Citation Marker [1], [2], etc. (No background, lifted slightly to align cleanly with font baseline)
    const citeMatch = token.match(/^\[(\d+)\]$/)
    if (citeMatch) {
      const markerNum = parseInt(citeMatch[1], 10)
      const matchedCitation =
        citations.find((c) => c.marker === markerNum) ?? citations[markerNum - 1]
      const quotesCount =
        matchedCitation?.quotes?.length ?? (matchedCitation?.quote ? 1 : 0)
      return (
        <button
          key={idx}
          type="button"
          onClick={() => {
            if (matchedCitation && onCiteClick) {
              onCiteClick(matchedCitation)
            }
          }}
          title={
            matchedCitation
              ? `Jump to ${matchedCitation.l}${quotesCount > 1 ? ` (${quotesCount} quotes)` : ""}`
              : `Citation [${markerNum}]`
          }
          className="relative top-[-1.5px] mx-0.5 inline cursor-pointer p-0 font-mono text-[12px] font-semibold text-(--cite,#E3A63F) transition-colors hover:text-(--acc,#52A8EA) hover:underline underline-offset-2 select-none"
        >
          [{markerNum}]
        </button>
      )
    }

    // Markdown Link [text](url)
    const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    if (linkMatch) {
      return (
        <a
          key={idx}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-(--acc,#52A8EA) underline underline-offset-2 transition-colors hover:text-(--tx,#DCE3EA)"
        >
          {linkMatch[1]}
        </a>
      )
    }

    return token
  })
}

export const MarkdownContent: React.FC<MarkdownContentProps> = ({
  content,
  citations = [],
  onCiteClick,
  className = "",
}) => {
  if (!content) return null

  // Split content into lines and group into markdown blocks
  const lines = content.split("\n")
  const blocks: React.ReactNode[] = []

  let inCodeBlock = false
  let codeBuffer: string[] = []
  let codeLang = ""

  let listBuffer: { type: "ul" | "ol"; items: string[] } | null = null

  const flushList = (keyPrefix: number) => {
    if (!listBuffer) return
    const isUl = listBuffer.type === "ul"
    const ListTag = isUl ? "ul" : "ol"
    blocks.push(
      <ListTag
        key={`list-${keyPrefix}`}
        className={`my-1.5 flex flex-col gap-1.5 pl-4 text-[13.5px] leading-relaxed ${
          isUl ? "list-disc" : "list-decimal"
        }`}
      >
        {listBuffer.items.map((item, iIdx) => (
          <li key={iIdx} className="text-(--tx,#DCE3EA)">
            {parseInline(item, citations, onCiteClick)}
          </li>
        ))}
      </ListTag>
    )
    listBuffer = null
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // 1. Code Block Fence (```lang)
    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        // End of code block
        blocks.push(
          <div
            key={`code-${i}`}
            className="my-2 overflow-x-auto rounded-lg border border-(--line,#25313E) bg-(--bg-bar,#101821) p-3 font-mono text-[12.5px] text-(--acc-tx-soft,#A8D4F2)"
          >
            {codeLang && (
              <div className="mb-1 text-[10px] font-medium tracking-wider text-(--tx-faint,#5C6976) uppercase">
                {codeLang}
              </div>
            )}
            <pre className="whitespace-pre">{codeBuffer.join("\n")}</pre>
          </div>
        )
        codeBuffer = []
        codeLang = ""
        inCodeBlock = false
      } else {
        flushList(i)
        inCodeBlock = true
        codeLang = trimmed.slice(3).trim()
      }
      continue
    }

    if (inCodeBlock) {
      codeBuffer.push(line)
      continue
    }

    // 2. Unordered List Items (- item or * item)
    const ulMatch = line.match(/^(\s*)[-*]\s+(.+)$/)
    if (ulMatch) {
      if (!listBuffer || listBuffer.type !== "ul") {
        flushList(i)
        listBuffer = { type: "ul", items: [] }
      }
      listBuffer.items.push(ulMatch[2])
      continue
    }

    // 3. Ordered List Items (1. item)
    const olMatch = line.match(/^(\s*)\d+\.\s+(.+)$/)
    if (olMatch) {
      if (!listBuffer || listBuffer.type !== "ol") {
        flushList(i)
        listBuffer = { type: "ol", items: [] }
      }
      listBuffer.items.push(olMatch[2])
      continue
    }

    // If not a list item, flush any open list
    flushList(i)

    // Empty line
    if (!trimmed) {
      continue
    }

    // 4. Horizontal Rule (--- or ***)
    if (/^(\*\*\*|---|___)$/.test(trimmed)) {
      blocks.push(
        <hr
          key={`hr-${i}`}
          className="my-2.5 border-t border-(--line-soft,#1B2530)"
        />
      )
      continue
    }

    // 5. Headers (# Header, ## Header, ### Header)
    if (trimmed.startsWith("#")) {
      const headerMatch = trimmed.match(/^(#{1,6})\s+(.+)$/)
      if (headerMatch) {
        const level = headerMatch[1].length
        const text = headerMatch[2]

        if (level === 1) {
          blocks.push(
            <h1
              key={`h1-${i}`}
              className="mt-3 mb-1 text-[16px] font-bold tracking-tight text-(--tx,#DCE3EA)"
            >
              {parseInline(text, citations, onCiteClick)}
            </h1>
          )
        } else if (level === 2) {
          blocks.push(
            <h2
              key={`h2-${i}`}
              className="mt-2.5 mb-1 text-[15px] font-semibold text-(--tx,#DCE3EA)"
            >
              {parseInline(text, citations, onCiteClick)}
            </h2>
          )
        } else {
          blocks.push(
            <h3
              key={`h3-${i}`}
              className="mt-2 mb-0.5 text-[14px] font-semibold text-(--acc,#52A8EA)"
            >
              {parseInline(text, citations, onCiteClick)}
            </h3>
          )
        }
        continue
      }
    }

    // 6. Blockquote (> Quote)
    if (trimmed.startsWith(">")) {
      const quoteText = trimmed.replace(/^>\s?/, "")
      blocks.push(
        <blockquote
          key={`quote-${i}`}
          className="my-1.5 border-l-2 border-(--acc,#52A8EA) pl-2.5 italic text-[13px] text-(--tx-dim,#8B98A7)"
        >
          {parseInline(quoteText, citations, onCiteClick)}
        </blockquote>
      )
      continue
    }

    // 7. Regular Paragraph
    blocks.push(
      <p key={`p-${i}`} className="my-1.5 leading-relaxed text-[13.5px] text-(--tx,#DCE3EA)">
        {parseInline(line, citations, onCiteClick)}
      </p>
    )
  }

  // Flush any trailing list or code
  flushList(lines.length)

  return (
    <div
      className={`space-y-1.5 text-[13.5px] leading-relaxed select-text ${className}`}
    >
      {blocks}
    </div>
  )
}

export default MarkdownContent
