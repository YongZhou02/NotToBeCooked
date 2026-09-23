import { useState } from "react"
import {
  AlertCircle,
  FilePenLine,
  FileText,
  FolderInput,
  MoreVertical,
  Play,
  Trash2,
} from "lucide-react"

import type { MockDocumentFile } from "../../types/course"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../dropdown-menu"
import { FileStatusBadge } from "./FileStatusBadge"
import { DeleteFileDialog } from "./DeleteFileDialog"
import { IndexingFailureDialog } from "./IndexingFailureDialog"
import { RenameFileDialog } from "./RenameFileDialog"
import { MoveFileDialog } from "./MoveFileDialog"

interface FileItemProps {
  file: MockDocumentFile
  folders: string[]
  isActive: boolean
  onOpenFile: (file: MockDocumentFile) => void
  onRenameFile: (fileId: string, newFileName: string) => Promise<void> | void
  onMoveFile: (
    fileId: string,
    destinationFolder: string
  ) => Promise<void> | void
  onRetryIndexing: (fileId: string) => Promise<void> | void
  onDeleteFile: (fileId: string) => Promise<void> | void
}

export function getFileExtension(filename: string): string {
  const parts = filename.split(".")
  return parts.length > 1 ? parts.pop()!.toLowerCase() : ""
}

export function FileIcon({
  filename,
  className,
}: {
  filename: string
  className?: string
}) {
  const ext = getFileExtension(filename)
  const defaultClasses = className || "h-4.5 w-4.5 shrink-0"

  switch (ext) {
    case "pdf":
      return (
        <svg
          viewBox="0 0 16 16"
          fill="none"
          className={`${defaultClasses} text-red-400/90`}
        >
          <path
            d="M4 2h5.5L13 5.5V14H4V2z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M9 2v4h4"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text
            x="5"
            y="11"
            fontSize="4"
            fontWeight="700"
            fill="currentColor"
            fontFamily="sans-serif"
          >
            PDF
          </text>
        </svg>
      )

    case "txt":
    case "md":
    case "markdown":
      return <FileText className={`${defaultClasses} text-blue-400/90`} />

    case "doc":
    case "docx":
      return (
        <svg
          viewBox="0 0 16 16"
          fill="none"
          className={`${defaultClasses} text-sky-400/90`}
        >
          <path
            d="M4 2h5.5L13 5.5V14H4V2z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text
            x="4.5"
            y="11"
            fontSize="3.8"
            fontWeight="700"
            fill="currentColor"
            fontFamily="sans-serif"
          >
            DOC
          </text>
        </svg>
      )

    case "ppt":
    case "pptx":
      return (
        <svg
          viewBox="0 0 16 16"
          fill="none"
          className={`${defaultClasses} text-amber-400/90`}
        >
          <path
            d="M4 2h5.5L13 5.5V14H4V2z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text
            x="4.8"
            y="11"
            fontSize="3.8"
            fontWeight="700"
            fill="currentColor"
            fontFamily="sans-serif"
          >
            PPT
          </text>
        </svg>
      )

    case "xls":
    case "xlsx":
    case "csv":
      return (
        <svg
          viewBox="0 0 16 16"
          fill="none"
          className={`${defaultClasses} text-emerald-400/90`}
        >
          <path
            d="M4 2h5.5L13 5.5V14H4V2z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M6 7.5h4M6 9.5h4M6 11.5h4"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
          />
        </svg>
      )

    case "py":
    case "ts":
    case "tsx":
    case "js":
    case "json":
      return (
        <svg
          viewBox="0 0 16 16"
          fill="none"
          className={`${defaultClasses} text-teal-400/90`}
        >
          <path
            d="M4 2h5.5L13 5.5V14H4V2z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M6.5 8l-1.5 1.5 1.5 1.5M9.5 8l1.5 1.5-1.5 1.5"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )

    default:
      return (
        <svg
          viewBox="0 0 16 16"
          fill="none"
          className={`${defaultClasses} text-(--tx-faint,#5C6976)`}
        >
          <path
            d="M4 2h5.5L13 5.5V14H4V2z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M9 2v4h4"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )
  }
}

export function FileItem({
  file,
  folders,
  isActive,
  onOpenFile,
  onRenameFile,
  onMoveFile,
  onRetryIndexing,
  onDeleteFile,
}: FileItemProps) {
  const [isRenameOpen, setIsRenameOpen] = useState(false)
  const [isMoveOpen, setIsMoveOpen] = useState(false)
  const [isFailureOpen, setIsFailureOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)

  return (
    <>
      <div
        className={`group relative flex h-10 w-full items-center rounded-sm border-l-[3px] transition-colors ${
          isActive
            ? "border-l-(--acc,#52A8EA) bg-(--acc,#52A8EA)/10 text-(--acc,#52A8EA)"
            : "border-l-transparent text-(--tx-dim,#8B98A7) hover:bg-(--bg-hover,#213040)/50 hover:text-(--tx,#DCE3EA)"
        }`}
      >
        <button
          type="button"
          onClick={() => onOpenFile(file)}
          aria-current={isActive ? "page" : undefined}
          className="flex h-full min-w-0 flex-1 cursor-pointer items-center gap-2 rounded-sm py-1 pr-1 pl-2 text-left focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-(--acc,#52A8EA) focus-visible:outline-none"
        >
          <FileIcon filename={file.name} />

          <span className="min-w-0 flex-1 truncate text-xs">{file.name}</span>

          <FileStatusBadge status={file.status ?? "ready"} />
        </button>

        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label={`Open actions for ${file.name}`}
            title={`Actions for ${file.name}`}
            className="mr-1 flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-sm text-(--tx-faint,#5C6976) transition-colors hover:bg-(--bg-hover,#213040) hover:text-(--tx,#DCE3EA) focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-(--acc,#52A8EA) focus-visible:outline-none"
          >
            <MoreVertical className="h-4 w-4" />
          </DropdownMenuTrigger>

          <DropdownMenuContent
            align="end"
            sideOffset={4}
            className="w-40 border-(--line,#25313E) bg-(--bg-panel,#121A23) text-(--tx,#DCE3EA)"
          >
            <DropdownMenuItem
              onClick={() => setIsRenameOpen(true)}
              className="cursor-pointer text-xs"
            >
              <FilePenLine className="h-4 w-4" />
              Rename
            </DropdownMenuItem>

            <DropdownMenuItem
              onClick={() => setIsMoveOpen(true)}
              className="cursor-pointer text-xs"
            >
              <FolderInput className="h-4 w-4" />
              Move
            </DropdownMenuItem>

            {file.status === "failed" && (
              <DropdownMenuItem
                onClick={() => setIsFailureOpen(true)}
                className="cursor-pointer text-xs text-(--danger-tx,#F0A19D)"
              >
                <AlertCircle className="h-4 w-4" />
                View failure details
              </DropdownMenuItem>
            )}
            {file.status === "uploaded" && (
              <DropdownMenuItem
                onClick={() => void onRetryIndexing(file.id)}
                className="cursor-pointer text-xs text-(--acc,#52A8EA)"
              >
                <Play className="h-4 w-4" />
                Start indexing
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => setIsDeleteOpen(true)}
              className="cursor-pointer text-xs text-(--danger-tx,#F0A19D)"
            >
              <Trash2 className="h-4 w-4" />
              Delete file
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {isRenameOpen && (
        <RenameFileDialog
          open
          fileName={file.name}
          onOpenChange={setIsRenameOpen}
          onRename={(newFileName) => onRenameFile(file.id, newFileName)}
        />
      )}
      {isMoveOpen && (
        <MoveFileDialog
          open
          fileName={file.name}
          currentFolder={file.category ?? "Uncategorized"}
          folders={folders}
          onOpenChange={setIsMoveOpen}
          onMove={(destinationFolder) => onMoveFile(file.id, destinationFolder)}
        />
      )}
      {isFailureOpen && (
        <IndexingFailureDialog
          open
          fileName={file.name}
          fileSize={file.size}
          errorMessage={file.errorMessage}
          onOpenChange={setIsFailureOpen}
          onRetry={() => onRetryIndexing(file.id)}
        />
      )}
      {isDeleteOpen && (
        <DeleteFileDialog
          open
          fileName={file.name}
          onOpenChange={setIsDeleteOpen}
          onDelete={() => onDeleteFile(file.id)}
        />
      )}
    </>
  )
}
