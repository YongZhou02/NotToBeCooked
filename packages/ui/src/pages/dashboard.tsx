import { useState, useMemo, useEffect } from "react"
import { useAuth } from "../context/auth-context"
import {
  useWorkspace,
  selectTabs,
  selectActiveCourse,
} from "../store/workspace"
import { useChatSession } from "../hooks/useChatSession"
import Chat, { type CitationItem } from "../components/chat/Chat"
import { groupCitations } from "../components/chat/ChatMessage"
import { TopBar } from "../components/topbar/TopBar"
import { FileExplorer } from "../components/explorer/FileExplorer"
import { RoadmapModal } from "../components/roadmap/RoadmapModal"
import { UploadModal } from "../components/upload/UploadModal"
import { TabBar } from "../components/tabs"
import { DocumentViewer } from "../components/workspace/DocumentViewer"
import { Maximize2, Minimize2, FileText } from "lucide-react"
import type { MockCourse, MockDocumentFile } from "../types/course"
import { useExplorerData } from "../hooks/useExplorerData"
import { useExplorerMutations } from "../hooks/useExplorerMutations"
import { toUiCourse, toUiFiles } from "../lib/explorerData"

export interface DashboardPageProps {
  platform?: "web" | "tauri"
}

/** Utility hook to manage an LRU list of IDs up to a maximum capacity */
function useLruList(
  activeItem: string | null,
  validItems: string[],
  maxCapacity = 4
): string[] {
  const [cached, setCached] = useState<string[]>([])
  const [prevActive, setPrevActive] = useState<string | null>(null)

  if (activeItem !== prevActive) {
    setPrevActive(activeItem)
    if (activeItem) {
      const validSet = new Set(validItems)
      const next = [
        activeItem,
        ...cached.filter((id) => id !== activeItem && validSet.has(id)),
      ].slice(0, maxCapacity)
      setCached(next)
    }
  }

  const validSet = new Set(validItems)
  return cached.filter((id) => validSet.has(id))
}

// ---------------------------------------------------------------------------
// Mock / Stub Course Catalog & File Repository for Development and Testing
// ---------------------------------------------------------------------------

const EMPTY_COURSE: MockCourse = {
  id: "",
  code: "—",
  name: "No course selected",
  year: 0,
  semester: 0,
  description: "",
  week: 0,
  weeks: 0,
  target: "",
  roadmap: [],
}

export function DashboardPage({ platform = "web" }: DashboardPageProps = {}) {
  const { user, logout } = useAuth()

  // Workspace Zustand store
  const activeCourseId = useWorkspace((s) => s.activeCourseId) || ""
  const switchCourse = useWorkspace((s) => s.switchCourse)
  const { coursesQuery, foldersQuery, filesQuery } =
    useExplorerData(activeCourseId)
  const {
    uploadFileMutation,
    updateFileMutation,
    deleteFileMutation,
    ingestFileMutation,
    createFolderMutation,
    updateFolderMutation,
    deleteFolderMutation,
  } = useExplorerMutations(activeCourseId)

  const courses = useMemo(
    () => (coursesQuery.data ?? []).map(toUiCourse),
    [coursesQuery.data]
  )
  const apiFolders = useMemo(() => foldersQuery.data ?? [], [foldersQuery.data])

  const apiCourseFiles = useMemo(
    () => toUiFiles(filesQuery.data ?? [], apiFolders),
    [apiFolders, filesQuery.data]
  )

  const explorerStatus =
    foldersQuery.isLoading || filesQuery.isLoading
      ? "loading"
      : foldersQuery.isError || filesQuery.isError
        ? "error"
        : "ready"
  const tabs = useWorkspace(selectTabs)
  const activeCourseWorkspace = useWorkspace(selectActiveCourse)
  const activeFileId =
    activeCourseWorkspace?.activeFileId ?? (tabs[0]?.fileId || null)
  const openTab = useWorkspace((s) => s.openTab)
  const renameFileReferences = useWorkspace((s) => s.renameFileReferences)
  const closeTab = useWorkspace((s) => s.closeTab)
  const setActiveFile = useWorkspace((s) => s.setActiveFile)
  const updateTabViewState = useWorkspace((s) => s.updateTabViewState)
  const openCitation = useWorkspace((s) => s.openCitation)

  // Repository of all files across all courses
  const allFiles = apiCourseFiles

  // Chat Session Hook
  const {
    sessions,
    messages,
    activeConversationId,
    isSending,
    sendMessage,
    deleteSession,
    selectSession,
    startNewChat,
  } = useChatSession(activeCourseId, allFiles)

  // Local UI states
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(
    null
  )
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const [isWorkspaceFullscreen, setIsWorkspaceFullscreen] =
    useState<boolean>(false)

  // Modals state (Roadmap & Upload)
  const [isRoadmapOpen, setIsRoadmapOpen] = useState(false)
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [uploadCategory, setUploadCategory] = useState<string>("Lecture Decks")
  const [isDirectFolderUpload, setIsDirectFolderUpload] = useState(false)

  // LRU Document Viewer Cache (keeps up to 4 recent document DOM trees mounted)
  const tabFileIds = useMemo(() => tabs.map((t) => t.fileId), [tabs])
  const cachedFileIds = useLruList(activeFileId, tabFileIds, 4)

  // Interactive Roadmap Milestone check state
  const [milestoneOverrides, setMilestoneOverrides] = useState<
    Record<string, Record<number, number>>
  >({})

  // Initialize course if not selected
  useEffect(() => {
    const activeCourseExists = courses.some(
      (course) => course.id === activeCourseId || course.code === activeCourseId
    )

    if (courses.length > 0 && !activeCourseExists) {
      switchCourse(courses[0]!.id)
    }
  }, [activeCourseId, courses, switchCourse])

  useEffect(() => {
    if (explorerStatus !== "ready") {
      return
    }

    const availableFileIds = new Set(allFiles.map((file) => file.id))

    for (const tab of tabs) {
      if (!availableFileIds.has(tab.fileId)) {
        closeTab(activeCourseId, tab.fileId)
      }
    }
  }, [activeCourseId, allFiles, closeTab, explorerStatus, tabs])

  // Current course metadata & files
  const currentCourse = useMemo(
    () =>
      courses.find(
        (course) =>
          course.id === activeCourseId || course.code === activeCourseId
      ) ??
      courses[0] ??
      EMPTY_COURSE,
    [activeCourseId, courses]
  )

  const apiFolderNames = useMemo(
    () => apiFolders.map((folder) => folder.name),
    [apiFolders]
  )

  const courseCategories = apiFolderNames

  const folderParents = useMemo(() => {
    const folderNamesById = new Map(
      apiFolders.map((folder) => [folder.id, folder.name])
    )

    return Object.fromEntries(
      apiFolders.map((folder) => [
        folder.name,
        folder.parent_folder_id
          ? (folderNamesById.get(folder.parent_folder_id) ?? null)
          : null,
      ])
    ) as Record<string, string | null>
  }, [apiFolders])

  const courseFiles = apiCourseFiles
  // Roadmap calculations (from workspace.html)
  const courseRoadmap = useMemo(() => {
    const base = currentCourse.roadmap
    const overrides = milestoneOverrides[currentCourse.id] || {}
    const overridesForCourse = overrides
    return base.map((m, idx) => ({
      ...m,
      s: overridesForCourse[idx] !== undefined ? overridesForCourse[idx]! : m.s,
    }))
  }, [currentCourse, milestoneOverrides])

  const roadmapStats = useMemo(() => {
    const total = courseRoadmap.length
    const done = courseRoadmap.filter((m) => m.s === 1).length
    const pct = total ? Math.round((done / total) * 100) : 0
    const nowItem =
      courseRoadmap.find((m) => m.now && m.s === 0) ||
      courseRoadmap.find((m) => m.s === 0)
    const nextText = total
      ? nowItem
        ? nowItem.n.split("—")[0]?.trim() || nowItem.n
        : "all clear"
      : "no milestones yet"

    return { done, total, pct, nextText }
  }, [courseRoadmap])

  const toggleMilestone = (idx: number) => {
    setMilestoneOverrides((prev) => {
      const courseMap = { ...(prev[currentCourse.id] || {}) }
      const currentVal =
        courseMap[idx] !== undefined
          ? courseMap[idx]
          : currentCourse.roadmap[idx]?.s || 0
      courseMap[idx] = currentVal === 1 ? 0 : 1
      return {
        ...prev,
        [currentCourse.id]: courseMap,
      }
    })
  }

  const showToast = (msg: string) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 3000)
  }

  const handleRenameFile = async (fileId: string, newFileName: string) => {
    await updateFileMutation.mutateAsync({
      fileId,
      data: {
        filename: newFileName,
      },
    })

    renameFileReferences(fileId, newFileName)
    showToast(`Renamed to ${newFileName}`)
  }

  const handleMoveFile = async (fileId: string, destinationFolder: string) => {
    const destination = apiFolders.find(
      (folder) => folder.name === destinationFolder
    )

    if (!destination) {
      throw new Error("Destination folder not found")
    }

    await updateFileMutation.mutateAsync({
      fileId,
      data: {
        folder_id: destination.id,
      },
    })

    showToast(`Moved file to ${destinationFolder}`)
  }

  const handleRetryIndexing = async (fileId: string) => {
    await ingestFileMutation.mutateAsync(fileId)
    showToast("Indexing restarted in the background")
  }

  const handleDeleteFile = async (fileId: string) => {
    const file = courseFiles.find((candidate) => candidate.id === fileId)

    if (!file) {
      throw new Error("File not found")
    }

    await deleteFileMutation.mutateAsync(fileId)

    closeTab(activeCourseId, fileId)
    setSelectedCitation((current) => (current?.f === fileId ? null : current))
    showToast(`Deleted ${file.name}`)
  }

  // Handlers for document & chat interaction
  const handleOpenFile = (file: MockDocumentFile) => {
    openTab(activeCourseId, {
      fileId: file.id,
      filename: file.name,
      page: null,
    })
    setSelectedCitation(null)
  }

  const handleCitationClick = (cite: CitationItem) => {
    setSelectedCitation(cite)
    const targetFile = allFiles.find((f) => f.id === cite.f) || {
      id: cite.f,
      name: cite.l.split(" · ")[0] || "Referenced Document.pdf",
    }

    openCitation(activeCourseId, cite.f, targetFile.name, cite.p)
  }

  const handleSendMessage = async (text: string) => {
    try {
      const normalizedText = text.trim().toLowerCase()

      const isDocumentSummary =
        normalizedText === "condense" ||
        normalizedText === "summarize this document" ||
        normalizedText === "summarise this document"

      if (isDocumentSummary && !activeFileId) {
        throw new Error("Open a document before requesting a summary")
      }

      const res = await sendMessage(text, {
        intent: isDocumentSummary ? "document_summary" : "question",
        fileIds: isDocumentSummary && activeFileId ? [activeFileId] : undefined,
      })
      if (res && res.answer) {
        return {
          text: res.answer,
          cites: groupCitations(
            res.citations as Array<Record<string, unknown>> | null | undefined
          ),
        }
      }
    } catch (error) {
      showToast(
        error instanceof Error
          ? `Couldn't send message: ${error.message}`
          : "Couldn't send message. Please try again."
      )
    }
  }

  const handleOpenDocumentFromChat = (fileId: string, page: number) => {
    const targetFile = allFiles.find((f) => f.id === fileId)
    openTab(activeCourseId, {
      fileId,
      filename: targetFile?.name || fileId,
      page,
    })
  }

  const handleOpenBatchUpload = () => {
    setUploadCategory("Lecture Decks")
    setIsDirectFolderUpload(false)
    setIsUploadModalOpen(true)
  }

  const handleOpenDirectFolderUpload = (category: string) => {
    setUploadCategory(category)
    setIsDirectFolderUpload(true)
    setIsUploadModalOpen(true)
  }

  const handleCreateSubfolder = async (
    parentFolder: string,
    folderName: string
  ) => {
    const parent = apiFolders.find((folder) => folder.name === parentFolder)

    if (!parent) {
      throw new Error("Parent folder not found")
    }

    await createFolderMutation.mutateAsync({
      name: folderName,
      parent_folder_id: parent.id,
      sort_order: apiFolders.length,
    })

    showToast(`Created ${folderName} inside ${parentFolder}`)
  }

  const handleCreateFolder = async (folderName: string) => {
    await createFolderMutation.mutateAsync({
      name: folderName,
      parent_folder_id: null,
      sort_order: apiFolders.length,
    })

    showToast(`Created ${folderName}`)
  }

  const handleRenameFolder = async (
    folderName: string,
    newFolderName: string
  ) => {
    const folder = apiFolders.find((candidate) => candidate.name === folderName)

    if (!folder) {
      throw new Error("Folder not found")
    }

    await updateFolderMutation.mutateAsync({
      folderId: folder.id,
      data: {
        name: newFolderName,
      },
    })

    showToast(`Renamed ${folderName} to ${newFolderName}`)
  }

  const handleDeleteFolder = async (folderName: string) => {
    const folder = apiFolders.find((candidate) => candidate.name === folderName)

    if (!folder) {
      throw new Error("Folder not found")
    }

    await deleteFolderMutation.mutateAsync(folder.id)

    showToast(`Deleted ${folderName}`)
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-(--bg-canvas,#161F29) font-sans text-(--tx,#DCE3EA) select-none">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-4 left-1/2 z-50 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 animate-in items-center gap-2 rounded-lg border border-(--acc,#52A8EA) bg-(--bg-raise,#1C2833) px-4 py-2 text-xs text-(--tx,#DCE3EA) shadow-lg duration-200 fade-in slide-in-from-bottom-2">
          <span className="h-2 w-2 rounded-full bg-(--acc,#52A8EA)" />
          <span className="min-w-0 break-words">{toastMessage}</span>
        </div>
      )}

      {/* Main Container */}
      <div className="flex h-full min-w-0 flex-1 flex-col">
        {/* Top Navbar Component */}
        <TopBar
          platform={platform}
          currentCourse={currentCourse}
          courses={courses}
          userEmail={user?.email}
          onSwitchCourse={(id) => switchCourse(id)}
          onLogout={() => logout()}
        />

        {/* Main 3-Pane Split View */}
        <div className="flex min-h-0 min-w-0 flex-1">
          {/* Left Pane: Structured File Explorer */}
          {!isWorkspaceFullscreen && (
            <FileExplorer
              categories={courseCategories}
              folderParents={folderParents}
              files={courseFiles}
              explorerStatus={explorerStatus}
              onRetryLoad={() => {
                void foldersQuery.refetch()
                void filesQuery.refetch()
              }}
              activeFileId={activeFileId}
              courseWeek={currentCourse.week}
              courseWeeks={currentCourse.weeks}
              roadmapProgressPct={roadmapStats.pct}
              nextMilestoneText={roadmapStats.nextText}
              onOpenFile={handleOpenFile}
              onRenameFile={handleRenameFile}
              onMoveFile={handleMoveFile}
              onRetryIndexing={handleRetryIndexing}
              onDeleteFile={handleDeleteFile}
              onOpenRoadmapModal={() => setIsRoadmapOpen(true)}
              onOpenBatchUpload={handleOpenBatchUpload}
              onOpenDirectFolderUpload={handleOpenDirectFolderUpload}
              onCreateFolder={handleCreateFolder}
              onCreateSubfolder={handleCreateSubfolder}
              onRenameFolder={handleRenameFolder}
              onDeleteFolder={handleDeleteFolder}
            />
          )}

          {/* Center Workspace: Tabs & Document Viewer */}
          <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-(--bg-canvas,#161F29)">
            {/* Tabs Bar */}
            <TabBar
              tabs={tabs}
              activeFileId={activeFileId}
              onSelectTab={(tab) => setActiveFile(activeCourseId, tab.fileId)}
              onCloseTab={(fileId) => closeTab(activeCourseId, fileId)}
              rightActions={
                <button
                  type="button"
                  onClick={() =>
                    setIsWorkspaceFullscreen(!isWorkspaceFullscreen)
                  }
                  title={
                    isWorkspaceFullscreen
                      ? "Restore normal view"
                      : "Full screen workspace"
                  }
                  className={`flex cursor-pointer items-center justify-center rounded-md p-1.5 transition-colors ${
                    isWorkspaceFullscreen
                      ? "bg-(--acc,#52A8EA)/15 text-(--acc,#52A8EA)"
                      : "text-(--tx-dim,#8B98A7) hover:bg-(--bg-hover,#213040) hover:text-white"
                  }`}
                >
                  {isWorkspaceFullscreen ? (
                    <Minimize2 className="h-3.5 w-3.5" />
                  ) : (
                    <Maximize2 className="h-3.5 w-3.5" />
                  )}
                </button>
              }
            />

            {/* Document Viewers (LRU DOM Cache) or Minimal Empty State */}
            {cachedFileIds.length > 0 && tabs.length > 0 ? (
              cachedFileIds.map((fileId) => {
                const doc = allFiles.find((f) => f.id === fileId)
                const tab = tabs.find((t) => t.fileId === fileId)
                if (!doc || !tab) return null

                return (
                  <DocumentViewer
                    key={fileId}
                    document={doc}
                    tab={tab}
                    isVisible={fileId === activeFileId}
                    onPageChange={(newPage) =>
                      updateTabViewState(activeCourseId, fileId, {
                        page: newPage,
                      })
                    }
                    onZoomChange={(newZoom) =>
                      updateTabViewState(activeCourseId, fileId, {
                        zoomLevel: newZoom,
                      })
                    }
                    selectedCitation={selectedCitation}
                    onDismissCitation={() => setSelectedCitation(null)}
                  />
                )
              })
            ) : (
              /* EMPTY / RECENT LECTURES CENTER VIEW (Minimalist & Borderless) */
              <div className="my-auto flex flex-1 flex-col items-center justify-center overflow-y-auto p-8 text-center">
                <div className="flex w-full max-w-md flex-col items-center gap-6">
                  <img
                    src="/ntbc-logo.png"
                    alt="NotToBeCooked Logo"
                    className="h-16 w-16 object-contain opacity-90"
                  />

                  {/* Recently Opened / Available Lectures List */}
                  {courseFiles.length > 0 && (
                    <div className="flex w-full flex-col items-center gap-2.5">
                      <span className="text-center font-mono text-[11px] font-semibold tracking-widest text-(--tx-faint,#5C6976) uppercase">
                        Recent Lectures & Materials
                      </span>
                      <div className="flex w-full flex-col gap-1">
                        {courseFiles.slice(0, 4).map((file) => (
                          <button
                            key={file.id}
                            type="button"
                            onClick={() => handleOpenFile(file)}
                            className="group flex cursor-pointer items-center justify-between gap-3 rounded-lg px-3.5 py-2 text-left transition-colors hover:bg-(--bg-hover,#213040)/50"
                          >
                            <div className="flex min-w-0 flex-1 items-center gap-2.5">
                              <FileText className="h-3.5 w-3.5 shrink-0 text-(--tx-faint,#5C6976) group-hover:text-(--acc,#52A8EA)" />
                              <span className="truncate text-xs font-medium text-(--tx-dim,#8B98A7) group-hover:text-(--tx,#DCE3EA)">
                                {file.name}
                              </span>
                            </div>
                            <span className="shrink-0 font-mono text-xs text-(--tx-faint,#5C6976) group-hover:text-(--tx-dim,#8B98A7)">
                              {file.size}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </main>

          {/* Right Pane: AI Chat Assistant */}
          {!isWorkspaceFullscreen && (
            <Chat
              courseCode={currentCourse.code}
              filesCount={courseFiles.length}
              files={courseFiles}
              categories={courseCategories}
              messages={messages}
              sessions={sessions}
              activeSessionId={activeConversationId}
              isTyping={isSending}
              onSendMessage={handleSendMessage}
              onSelectSession={(id) => selectSession(id)}
              onDeleteSession={(id) => deleteSession(id)}
              onNewChat={() => startNewChat()}
              onOpenDocument={handleOpenDocumentFromChat}
              onCiteClick={handleCitationClick}
            />
          )}
        </div>
      </div>

      {/* Learning Roadmap Modal Component */}
      <RoadmapModal
        isOpen={isRoadmapOpen}
        course={currentCourse}
        roadmap={courseRoadmap}
        progressPct={roadmapStats.pct}
        doneCount={roadmapStats.done}
        totalCount={roadmapStats.total}
        onToggleMilestone={toggleMilestone}
        onClose={() => setIsRoadmapOpen(false)}
      />

      {/* Batch / Direct Folder Upload Modal Component */}
      <UploadModal
        isOpen={isUploadModalOpen}
        courseCode={currentCourse.code}
        categories={courseCategories}
        initialCategory={uploadCategory}
        isDirectFolderUpload={isDirectFolderUpload}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={async (category, file) => {
          const destinationFolder = apiFolders.find(
            (folder) => folder.name === category
          )

          if (!destinationFolder) {
            throw new Error(`Folder not found: ${category}`)
          }

          const uploadedFile = await uploadFileMutation.mutateAsync({
            folderId: destinationFolder.id,
            file,
          })

          try {
            await ingestFileMutation.mutateAsync(uploadedFile.id)
            showToast(`Uploaded ${file.name}. Indexing started.`)
          } catch {
            showToast(
              `Uploaded ${file.name}, but indexing could not start. Retry from the file menu.`
            )
          }
        }}
      />
    </div>
  )
}

export default DashboardPage
