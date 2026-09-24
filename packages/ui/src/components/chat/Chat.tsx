import React, { useState, useRef, useEffect, useMemo } from "react"
import {
  ChatMessageItem,
  type ChatMessage,
  type CitationItem,
} from "./ChatMessage"
import { ChatInput, type ChatFile } from "./ChatInput"
import { History, type ChatSessionItem } from "./History"
import { CitationDrawer } from "./CitationDrawer"
import { Plus, Clock, Trash2, GripVertical, X } from "lucide-react"

export type { CitationItem, ChatMessage, ChatFile, ChatSessionItem }

export interface ChatProps {
  courseCode?: string
  filesCount?: number
  files?: ChatFile[]
  categories?: string[]
  quickPrompts?: string[]
  scopeFile?: ChatFile | null

  // Controlled or uncontrolled message state
  messages?: ChatMessage[]
  initialMessages?: ChatMessage[]

  // Controlled session history state
  sessions?: ChatSessionItem[]
  activeSessionId?: string | null
  activeSessionTitle?: string | null

  // Loading & State
  isTyping?: boolean

  // Callbacks
  onSendMessage?: (
    text: string
  ) =>
    | Promise<{ text: string; cites?: CitationItem[] } | void>
    | { text: string; cites?: CitationItem[] }
    | void
  onCiteClick?: (cite: CitationItem) => void
  onSelectSession?: (sessionId: string) => void
  onDeleteSession?: (sessionId: string) => void
  onNewChat?: () => void
  onClearChat?: () => void
  onOpenDocument?: (fileId: string, page: number) => void
  onClearFileScope?: () => void

  className?: string
}

export const Chat: React.FC<ChatProps> = ({
  courseCode = "CS202",
  filesCount = 9,
  files = [
    { id: "cs202-lec4", name: "Lecture 4.pdf", category: "Lecture Decks" },
    { id: "cs202-lab3", name: "Lab 3.pdf", category: "Lab Handouts" },
    { id: "cs202-tut1", name: "Tutorial 1.pdf", category: "Tutorials & PYQs" },
    {
      id: "cs202-planner",
      name: "Course Planner.pdf",
      category: "Course Planner",
    },
  ],
  categories = [
    "Course Planner",
    "Lecture Decks",
    "Lab Handouts",
    "Tutorials & PYQs",
  ],
  quickPrompts = ["Condense", "Quiz me", "Simplify", "Storyboard"],
  scopeFile = null,
  messages: controlledMessages,
  initialMessages,
  sessions = [],
  activeSessionId,
  activeSessionTitle,
  isTyping: controlledIsTyping,
  onSendMessage,
  onCiteClick,
  onSelectSession,
  onDeleteSession,
  onNewChat,
  onClearChat,
  onOpenDocument,
  onClearFileScope,
  className = "",
}) => {
  // Horizontal Resizing State
  const [width, setWidth] = useState<number>(340)
  const [isResizing, setIsResizing] = useState(false)

  // History Drawer State
  const [historyOpen, setHistoryOpen] = useState(false)

  // Selected Citation State for preview drawer
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(
    null
  )

  // Local fallback state when uncontrolled
  const [localCourseMessagesMap, setLocalCourseMessagesMap] = useState<
    Record<string, ChatMessage[]>
  >({})
  const [localIsTyping, setLocalIsTyping] = useState(false)

  const msgsEndRef = useRef<HTMLDivElement>(null)

  // Determine current active messages (controlled takes precedence)
  const currentMessages = useMemo(() => {
    if (controlledMessages !== undefined) return controlledMessages
    return localCourseMessagesMap[courseCode] ?? initialMessages ?? []
  }, [controlledMessages, localCourseMessagesMap, courseCode, initialMessages])

  // Active conversation title lookup
  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId),
    [sessions, activeSessionId]
  )
  const headerTitle = activeSessionTitle ?? activeSession?.title ?? ""

  const isTyping =
    controlledIsTyping !== undefined ? controlledIsTyping : localIsTyping

  // Horizontal Drag Resizing effect
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
  }

  const handleResizeKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 40 : 16

    if (e.key === "ArrowLeft") {
      e.preventDefault()
      setWidth((currentWidth) => Math.min(800, currentWidth + step))
    } else if (e.key === "ArrowRight") {
      e.preventDefault()
      setWidth((currentWidth) => Math.max(280, currentWidth - step))
    }
  }
  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX
      if (newWidth >= 280 && newWidth <= 800) {
        setWidth(newWidth)
      }
    }

    const handleMouseUp = () => {
      setIsResizing(false)
    }

    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", handleMouseUp)
    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isResizing])

  const scrollToBottom = () => {
    msgsEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [currentMessages, isTyping, courseCode])

  const handleSend = async (fullQuery: string) => {
    if (!fullQuery.trim() || isTyping) return

    if (controlledMessages === undefined) {
      // Uncontrolled local update
      const userMsg: ChatMessage = {
        r: "me",
        role: "user",
        x: fullQuery,
        content: fullQuery,
      }
      setLocalCourseMessagesMap((prev) => ({
        ...prev,
        [courseCode]: [...(prev[courseCode] ?? initialMessages ?? []), userMsg],
      }))
    }

    if (onSendMessage) {
      if (controlledIsTyping === undefined) setLocalIsTyping(true)
      try {
        const res = await onSendMessage(fullQuery)
        if (controlledIsTyping === undefined) setLocalIsTyping(false)
        if (res && res.text && controlledMessages === undefined) {
          setLocalCourseMessagesMap((prev) => ({
            ...prev,
            [courseCode]: [
              ...(prev[courseCode] ?? initialMessages ?? []),
              {
                r: "ai",
                role: "assistant",
                x: res.text,
                content: res.text,
                cites: res.cites,
                citations: res.cites,
              },
            ],
          }))
        }
      } catch {
        if (controlledIsTyping === undefined) setLocalIsTyping(false)
      }
    } else {
      // Fallback mock response if no handler provided
      setLocalIsTyping(true)
      setTimeout(() => {
        setLocalIsTyping(false)
        const responseText = `I found grounded material in <b>${courseCode}</b> related to your query. You can inspect the citations below to view the source passage.`
        const responseCites: CitationItem[] = [
          {
            f: files[0]?.id || "f1",
            p: 1,
            l: `${files[0]?.name || "Document"} · p.1`,
            quote:
              "Key foundational definitions and theorems from the core syllabus.",
          },
        ]

        setLocalCourseMessagesMap((prev) => ({
          ...prev,
          [courseCode]: [
            ...(prev[courseCode] ?? initialMessages ?? []),
            {
              r: "ai",
              role: "assistant",
              x: responseText,
              content: responseText,
              cites: responseCites,
              citations: responseCites,
            },
          ],
        }))
      }, 600)
    }
  }

  const handleClear = () => {
    if (controlledMessages === undefined) {
      setLocalCourseMessagesMap((prev) => ({
        ...prev,
        [courseCode]: [],
      }))
    }
    setSelectedCitation(null)
    onClearChat?.()
  }

  const handleDeleteCurrentConversation = () => {
    if (activeSessionId && onDeleteSession) {
      onDeleteSession(activeSessionId)
      setSelectedCitation(null)
    } else {
      handleClear()
    }
  }

  const handleCitationClick = (cite: CitationItem) => {
    setSelectedCitation(cite)
    onCiteClick?.(cite)
  }

  const handleNewChatClick = () => {
    if (onNewChat) {
      onNewChat()
    } else {
      handleClear()
    }
  }

  return (
    <div className="relative flex h-full min-h-0 flex-none">
      {/* Horizontal Drag Resize Handle */}
      <div
        role="separator"
        aria-label="Resize Chat panel"
        aria-orientation="vertical"
        aria-valuemin={280}
        aria-valuemax={800}
        aria-valuenow={width}
        tabIndex={0}
        onMouseDown={handleMouseDown}
        onKeyDown={handleResizeKeyDown}
        className={`group relative z-10 w-2 flex-none cursor-col-resize transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-(--acc,#52A8EA) ${
          isResizing ? "bg-(--acc,#52A8EA)/35" : "bg-(--line,#25313E)"
        }`}
        title="Drag horizontally or use Left and Right arrow keys to resize Chat panel"
      >
        <span className="pointer-events-none absolute top-1/2 left-1/2 flex h-10 w-3 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-(--line,#25313E) bg-(--bg-raise,#1C2833) text-(--tx-faint,#5C6976) opacity-45 shadow-sm transition-all group-hover:border-(--acc,#52A8EA) group-hover:text-(--acc,#52A8EA) group-hover:opacity-100 group-focus-visible:border-(--acc,#52A8EA) group-focus-visible:text-(--acc,#52A8EA) group-focus-visible:opacity-100">
          <GripVertical aria-hidden="true" className="h-4 w-4" />
        </span>
      </div>

      {/* Main Chat Panel */}
      <aside
        style={{ width: `${width}px` }}
        className={`relative flex min-h-0 flex-col bg-(--bg-panel,#121A23) text-xs text-(--tx,#DCE3EA) select-none ${className}`}
      >
        {/* Top Header */}
        <div className="flex h-10 flex-none items-center justify-between gap-2 border-b border-(--line-soft,#1B2530) bg-(--bg-bar,#101821)/50 px-3">
          <span className="min-w-0 flex-1 truncate text-xs font-medium text-(--tx,#DCE3EA)">
            {headerTitle}
          </span>

          <div className="flex flex-none items-center gap-1">
            {/* New Chat Button */}
            <button
              type="button"
              onClick={handleNewChatClick}
              title="Start new conversation"
              className="flex h-6 w-6 cursor-pointer items-center justify-center rounded text-(--tx-dim,#8B98A7) transition-colors hover:bg-(--bg-hover,#213040) hover:text-(--tx,#DCE3EA)"
            >
              <Plus className="h-4 w-4" />
            </button>

            {/* History Drawer Toggle Button */}
            <button
              type="button"
              onClick={() => setHistoryOpen(!historyOpen)}
              title="Toggle Chat History"
              className={`flex h-6 w-6 cursor-pointer items-center justify-center rounded transition-colors ${
                historyOpen
                  ? "bg-(--bg-hover,#213040) text-(--acc,#52A8EA)"
                  : "text-(--tx-dim,#8B98A7) hover:bg-(--bg-hover,#213040) hover:text-(--tx,#DCE3EA)"
              }`}
            >
              <Clock className="h-4 w-4" />
            </button>

            {/* Delete / Clear Chat Button */}
            <button
              type="button"
              onClick={handleDeleteCurrentConversation}
              title={
                activeSessionId
                  ? "Delete current conversation"
                  : "Clear conversation"
              }
              className="flex h-6 w-6 cursor-pointer items-center justify-center rounded text-(--tx-dim,#8B98A7) transition-colors hover:bg-destructive/10 hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {scopeFile && (
          <div className="flex flex-none items-center gap-1.5 border-b border-(--line-soft,#1B2530) px-3 py-2 text-[11px] text-(--tx-dim,#8B98A7)">
            <span className="shrink-0">Asking:</span>
            <span className="min-w-0 flex-1 truncate font-medium text-(--tx,#DCE3EA)">
              {scopeFile.name}
            </span>
            <button
              type="button"
              onClick={onClearFileScope}
              aria-label={"Ask the whole course instead of " + scopeFile.name}
              title="Ask the whole course"
              className="flex h-5 w-5 shrink-0 cursor-pointer items-center justify-center rounded text-(--tx-dim,#8B98A7) hover:bg-(--bg-hover,#213040) hover:text-(--tx,#DCE3EA)"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* History Drawer Overlay */}
        <History
          sessions={sessions}
          activeSessionId={activeSessionId}
          isOpen={historyOpen}
          onClose={() => setHistoryOpen(false)}
          onSelectSession={(id) => onSelectSession?.(id)}
          onDeleteSession={(id) => onDeleteSession?.(id)}
          onNewChat={handleNewChatClick}
        />

        {/* Messages Container */}
        <div className="flex min-h-0 flex-1 scrollbar-thin [scrollbar-color:var(--line,#25313E)_transparent] flex-col overflow-y-auto p-3 select-text [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-(--line,#25313E) [&::-webkit-scrollbar-track]:bg-transparent">
          {currentMessages.length === 0 ? (
            /* WELCOME HERO SCREEN */
            <div className="my-auto flex flex-1 animate-in flex-col items-center justify-center gap-3 p-3 text-center duration-300 fade-in">
              <img
                src="/ntbc-logo.png"
                alt="NotToBeCooked Logo"
                className="h-12 w-12 object-contain"
              />

              <div className="flex max-w-xs flex-col gap-1">
                <h3 className="text-base font-semibold tracking-tight text-(--tx,#DCE3EA)">
                  Ask anything about{" "}
                  <span className="font-bold text-(--acc,#52A8EA)">
                    {courseCode}
                  </span>
                </h3>
                <p className="text-xs leading-relaxed text-(--tx-dim,#8B98A7)">
                  Explore lectures, labs, and notes across{" "}
                  <span className="font-medium text-(--tx,#DCE3EA)">
                    {filesCount} course files
                  </span>
                  .
                </p>
              </div>

              {quickPrompts.length > 0 && (
                <div className="mt-2 flex w-full max-w-xs flex-col gap-1">
                  {quickPrompts.map((q, idx) => (
                    <button
                      key={idx}
                      type="button"
                      disabled={isTyping}
                      onClick={() => handleSend(q)}
                      className="group flex cursor-pointer items-center justify-between rounded-lg border border-(--line,#25313E) bg-(--bg-raise,#1C2833) px-2.5 py-1.5 text-left text-xs text-(--tx-dim,#8B98A7) transition-colors hover:border-(--acc-deep,#1D5D8A) hover:text-(--tx,#DCE3EA) focus-visible:border-(--acc,#52A8EA) focus-visible:ring-2 focus-visible:ring-(--acc,#52A8EA)/40 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <span>{q}</span>
                      <span className="text-(--tx-faint,#5C6976) transition-colors group-hover:text-(--acc,#52A8EA)">
                        ↗
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* CONVERSATION STREAM */
            <div className="flex flex-col gap-3">
              {currentMessages.map((m, idx) => (
                <ChatMessageItem
                  key={m.id || idx}
                  message={m}
                  onCiteClick={handleCitationClick}
                />
              ))}

              {/* Typing indicator */}
              {isTyping && (
                <div className="flex w-full items-center py-1">
                  <div className="flex gap-1.5 py-0.5">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-(--acc,#52A8EA)" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-(--acc,#52A8EA) [animation-delay:0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-(--acc,#52A8EA) [animation-delay:0.3s]" />
                  </div>
                </div>
              )}
            </div>
          )}
          <div ref={msgsEndRef} />
        </div>

        {/* Selected Citation Preview Drawer */}
        <CitationDrawer
          citation={selectedCitation}
          onClose={() => setSelectedCitation(null)}
          onOpenDocument={onOpenDocument}
        />

        {/* Input Composer */}
        <div className="flex-none p-2.5 pt-1">
          <ChatInput
            files={files}
            categories={categories}
            quickPrompts={currentMessages.length > 0 ? quickPrompts : []}
            isTyping={isTyping}
            onSend={handleSend}
          />
        </div>
      </aside>
    </div>
  )
}

export default Chat
