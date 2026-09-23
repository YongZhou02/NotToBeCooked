import React, { useState, useMemo, useEffect } from "react"
import type { MockDocumentFile } from "../../types/course"
import { FolderItem } from "./FolderItem"
import { FileItem } from "./FileItem"
import { Folder, FolderPlus, Search, X } from "lucide-react"
import { RoadmapWidget } from "../roadmap/RoadmapWidget"
import { UploadDock } from "../upload/UploadDock"
import { ExplorerState } from "./ExplorerState"
import { CreateFolderDialog } from "./CreateFolderDialog"

export type ExplorerStatus = "ready" | "loading" | "error"
interface FileExplorerProps {
  categories: string[]
  folderParents: Record<string, string | null>
  files: MockDocumentFile[]
  activeFileId: string | null
  courseWeek: number
  courseWeeks: number
  roadmapProgressPct: number
  nextMilestoneText: string
  onOpenFile: (file: MockDocumentFile) => void
  onOpenRoadmapModal: () => void
  onOpenBatchUpload: () => void
  onOpenDirectFolderUpload: (category: string) => void
  onCreateFolder: (folderName: string) => Promise<void> | void
  onCreateSubfolder: (
    parentFolder: string,
    folderName: string
  ) => Promise<void> | void
  onRenameFolder: (
    folderName: string,
    newFolderName: string
  ) => Promise<void> | void
  onDeleteFolder: (folderName: string) => Promise<void> | void
  className?: string
  onRenameFile: (fileId: string, newFileName: string) => Promise<void> | void
  onMoveFile: (
    fileId: string,
    destinationFolder: string
  ) => Promise<void> | void
  onRetryIndexing: (fileId: string) => Promise<void> | void
  onDeleteFile: (fileId: string) => Promise<void> | void
  explorerStatus?: ExplorerStatus
  onRetryLoad?: () => void
}

export function FileExplorer({
  categories,
  folderParents,
  files,
  explorerStatus = "ready",
  onRetryLoad,
  activeFileId,
  courseWeek,
  courseWeeks,
  roadmapProgressPct,
  nextMilestoneText,
  onOpenFile,
  onRenameFile,
  onMoveFile,
  onRetryIndexing,
  onDeleteFile,
  onOpenRoadmapModal,
  onOpenBatchUpload,
  onOpenDirectFolderUpload,
  onCreateFolder,
  onCreateSubfolder,
  onRenameFolder,
  onDeleteFolder,
  className = "",
}: FileExplorerProps) {
  // Horizontal Resizing State (Matching Chat.tsx dynamic width behavior)
  const [width, setWidth] = useState<number>(300)
  const [isResizing, setIsResizing] = useState(false)

  const [searchQuery, setSearchQuery] = useState("")
  const [isCreateFolderOpen, setIsCreateFolderOpen] = useState(false)
  const [collapsedCats, setCollapsedCats] = useState<Record<string, boolean>>(
    {}
  )

  // Horizontal Drag Resizing effect
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
  }

  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = e.clientX
      if (newWidth >= 220 && newWidth <= 600) {
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

  // Filtered files based on search
  const filteredFiles = useMemo(() => {
    if (!searchQuery.trim()) return files
    const q = searchQuery.toLowerCase()
    return files.filter(
      (f) =>
        f.name.toLowerCase().includes(q) ||
        (f.category && f.category.toLowerCase().includes(q))
    )
  }, [files, searchQuery])

  const visibleCategories = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()

    if (!query) return categories

    return categories.filter(
      (category) =>
        category.toLowerCase().includes(query) ||
        filteredFiles.some((file) => file.category === category)
    )
  }, [categories, filteredFiles, searchQuery])

  const rootCategories = useMemo(
    () =>
      visibleCategories.filter((category) => {
        const parentFolder = folderParents[category]
        return !parentFolder || !visibleCategories.includes(parentFolder)
      }),
    [folderParents, visibleCategories]
  )

  const toggleCategory = (cat: string) => {
    setCollapsedCats((prev) => ({
      ...prev,
      [cat]: !prev[cat],
    }))
  }

  const renderFolder = (category: string): React.ReactNode => {
    const totalFilesInFolder = files.filter(
      (file) => file.category === category
    )
    const visibleFilesInFolder = filteredFiles.filter(
      (file) => file.category === category
    )
    const childFolders = visibleCategories.filter(
      (folderName) => folderParents[folderName] === category
    )
    const isCollapsed = collapsedCats[category] || false
    const isEmpty = totalFilesInFolder.length === 0 && childFolders.length === 0

    return (
      <FolderItem
        key={category}
        category={category}
        fileCount={totalFilesInFolder.length}
        childFolderCount={childFolders.length}
        isCollapsed={isCollapsed}
        onToggle={() => toggleCategory(category)}
        onDirectUpload={onOpenDirectFolderUpload}
        onCreateSubfolder={onCreateSubfolder}
        onRenameFolder={onRenameFolder}
        onDeleteFolder={onDeleteFolder}
      >
        {isEmpty ? (
          <ExplorerState
            variant="empty"
            folderName={category}
            onUpload={() => onOpenDirectFolderUpload(category)}
          />
        ) : (
          <>
            {visibleFilesInFolder.map((file) => (
              <FileItem
                key={file.id}
                file={file}
                folders={categories}
                isActive={activeFileId === file.id}
                onOpenFile={onOpenFile}
                onRenameFile={onRenameFile}
                onMoveFile={onMoveFile}
                onRetryIndexing={onRetryIndexing}
                onDeleteFile={onDeleteFile}
              />
            ))}
            {childFolders.map(renderFolder)}
          </>
        )}
      </FolderItem>
    )
  }

  return (
    <div className="relative flex h-full min-h-0 flex-none select-none">
      <aside
        style={{ width: `${width}px` }}
        className={`flex min-h-0 flex-col bg-(--bg-panel,#121A23) text-xs text-(--tx,#DCE3EA) ${className}`}
      >
        {/* File Explorer Header & Search */}
        <div className="flex flex-col gap-2 border-b border-(--line-soft,#1B2530) p-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-semibold tracking-wider text-(--tx-dim,#8B98A7) uppercase">
              <Folder className="h-3.5 w-3.5 text-(--acc,#52A8EA)" />
              Explorer
            </span>
            <span className="font-mono text-xs text-(--tx-faint,#5C6976)">
              {files.length} files
            </span>
          </div>

          {/* Minimalist Search Box */}
          <div className="flex items-center gap-2 rounded-lg border border-(--line,#25313E) bg-(--bg-raise,#1C2833)/80 px-2.5 py-1.5 text-xs focus-within:border-(--acc,#52A8EA) focus-within:ring-1 focus-within:ring-(--acc,#52A8EA)/40">
            <Search className="h-3.5 w-3.5 text-(--tx-faint,#5C6976)" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents..."
              disabled={explorerStatus !== "ready"}
              aria-label="Search folders and files"
              className="w-full bg-transparent text-xs text-(--tx,#DCE3EA) outline-none placeholder:text-(--tx-faint,#5C6976) disabled:cursor-not-allowed disabled:opacity-50"
            />
            {searchQuery && explorerStatus === "ready" && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
                title="Clear search"
                className="flex h-5 w-5 shrink-0 cursor-pointer items-center justify-center rounded-sm text-(--tx-faint,#5C6976) hover:bg-(--bg-hover,#213040) hover:text-(--tx,#DCE3EA) focus-visible:ring-2 focus-visible:ring-(--acc,#52A8EA) focus-visible:outline-none"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Tree View Container: Categories & Files */}
        <div className="flex min-h-0 flex-1 scrollbar-thin [scrollbar-color:var(--line,#25313E)_transparent] flex-col gap-2 overflow-y-auto p-2.5">
          {explorerStatus === "loading" ? (
            <ExplorerState variant="loading" />
          ) : explorerStatus === "error" ? (
            <ExplorerState
              variant="error"
              onRetry={() => {
                onRetryLoad?.()
              }}
            />
          ) : searchQuery.trim() && visibleCategories.length === 0 ? (
            <ExplorerState
              variant="no-results"
              query={searchQuery.trim()}
              onClear={() => setSearchQuery("")}
            />
          ) : (
            <>
              <div className="flex items-center justify-between px-1 font-mono text-[11px] font-semibold tracking-wider text-(--tx-faint,#5C6976) uppercase">
                <span>Folders</span>
                <button
                  type="button"
                  onClick={() => setIsCreateFolderOpen(true)}
                  aria-label="Create root folder"
                  title="Create folder"
                  className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-(--tx-muted,#93A1AF) transition-colors hover:bg-(--bg-hover,#213040) hover:text-(--acc,#52A8EA) focus-visible:ring-2 focus-visible:ring-(--acc,#52A8EA) focus-visible:outline-none"
                >
                  <FolderPlus className="h-4 w-4" />
                </button>
              </div>

              {rootCategories.length === 0 ? (
                <ExplorerState
                  variant="empty"
                  onCreateFolder={() => setIsCreateFolderOpen(true)}
                />
              ) : (
                <div className="flex flex-col gap-1.5">
                  {rootCategories.map(renderFolder)}
                </div>
              )}
            </>
          )}
        </div>
        {/* Bottom Explorer: Unified Minimalist Roadmap & Upload Dock */}
        <div className="flex flex-col gap-2.5 border-t border-(--line,#25313E) bg-(--bg-bar,#101821)/70 p-3">
          <RoadmapWidget
            week={courseWeek}
            weeks={courseWeeks}
            progressPct={roadmapProgressPct}
            nextMilestoneText={nextMilestoneText}
            onOpenRoadmap={onOpenRoadmapModal}
          />
          <UploadDock onOpenBatchUpload={onOpenBatchUpload} />
        </div>
      </aside>

      <CreateFolderDialog
        open={isCreateFolderOpen}
        onOpenChange={setIsCreateFolderOpen}
        onCreate={onCreateFolder}
      />

      {/* Horizontal Drag Resize Handle on Right Edge */}
      <div
        role="separator"
        tabIndex={0}
        aria-label="Resize File Explorer"
        aria-orientation="vertical"
        aria-valuemin={220}
        aria-valuemax={600}
        aria-valuenow={width}
        onMouseDown={handleMouseDown}
        onKeyDown={(event) => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return
          event.preventDefault()
          const direction = event.key === "ArrowLeft" ? -20 : 20
          setWidth((current) =>
            Math.min(600, Math.max(220, current + direction))
          )
        }}
        className={`relative z-10 w-1.5 flex-none cursor-col-resize transition-colors hover:bg-(--acc,#52A8EA) focus-visible:bg-(--acc,#52A8EA) focus-visible:outline-none ${
          isResizing ? "bg-(--acc,#52A8EA)" : "bg-(--line,#25313E)"
        }`}
        title="Drag or use arrow keys to resize File Explorer"
      />
    </div>
  )
}
