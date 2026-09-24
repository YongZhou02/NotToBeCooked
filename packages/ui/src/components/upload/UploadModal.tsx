import { useRef, useState, type DragEvent } from "react"
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  LoaderCircle,
  Trash2,
  Upload,
  UploadCloud,
} from "lucide-react"

import { Button } from "../button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../dialog"

type UploadStage = "initial" | "selected" | "uploading" | "complete"

const MAX_FILE_SIZE = 50 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(["pdf", "md", "markdown", "doc", "docx"])

function fileKey(file: File): string {
  return `${file.name}:${file.size}`
}

function fileExtension(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() ?? ""
}

interface UploadModalProps {
  isOpen: boolean
  courseCode: string
  categories: string[]
  initialCategory?: string
  isDirectFolderUpload?: boolean
  onClose: () => void
  onUploadSuccess: (category: string, file: File) => Promise<void>
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function UploadModal({
  isOpen,
  courseCode,
  categories,
  initialCategory,
  isDirectFolderUpload = false,
  onClose,
  onUploadSuccess,
}: UploadModalProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [categoryOverride, setCategoryOverride] = useState<string | null>(null)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [stage, setStage] = useState<UploadStage>("initial")
  const [isDragging, setIsDragging] = useState(false)
  const [validationMessages, setValidationMessages] = useState<string[]>([])
  const [requestError, setRequestError] = useState<string | null>(null)

  const requestedCategory = categoryOverride ?? initialCategory
  const selectedCategory =
    (requestedCategory && categories.includes(requestedCategory)
      ? requestedCategory
      : categories[0]) ?? ""

  const resetAndClose = () => {
    if (stage === "uploading") return
    setCategoryOverride(null)
    setSelectedFiles([])
    setStage("initial")
    setIsDragging(false)
    onClose()
  }

  const addFiles = (files: File[]) => {
    if (files.length === 0 || stage === "uploading") return

    const messages: string[] = []
    const known = new Set(selectedFiles.map(fileKey))
    const accepted: File[] = []

    files.forEach((file) => {
      if (!ALLOWED_EXTENSIONS.has(fileExtension(file.name))) {
        messages.push(`${file.name}: unsupported file type.`)
        return
      }
      if (file.size > MAX_FILE_SIZE) {
        messages.push(`${file.name}: exceeds the 50 MB limit.`)
        return
      }
      if (known.has(fileKey(file))) {
        messages.push(`${file.name}: already selected.`)
        return
      }

      known.add(fileKey(file))
      accepted.push(file)
    })

    if (accepted.length > 0) {
      setSelectedFiles((current) => [...current, ...accepted])
      setStage("selected")
    }
    setValidationMessages(messages)
    setRequestError(null)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    addFiles(Array.from(event.dataTransfer.files))
  }

  const removeFile = (fileToRemove: File) => {
    setSelectedFiles((current) => {
      const next = current.filter((file) => file !== fileToRemove)
      if (next.length === 0) setStage("initial")
      return next
    })
  }

  const handleUpload = async () => {
    if (selectedFiles.length === 0 || stage === "uploading") return
    setRequestError(null)
    setStage("uploading")

    try {
      await Promise.all(
        selectedFiles.map((file) => onUploadSuccess(selectedCategory, file))
      )
      setStage("complete")
    } catch (error) {
      setRequestError(
        error instanceof Error && error.message.trim()
          ? error.message
          : "Couldn’t upload these files. Check your connection and try again."
      )
      setStage("selected")
    }
  }

  const totalSize = selectedFiles.reduce((sum, file) => sum + file.size, 0)

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && resetAndClose()}>
      <DialogContent className="w-[calc(100vw-2rem)] max-w-lg min-w-0 gap-0 overflow-hidden border-(--line,#25313E) bg-(--bg-panel,#121A23) p-0 text-(--tx,#DCE3EA) shadow-2xl">
        <DialogHeader className="border-b border-(--line-soft,#1B2530) px-5 py-4">
          <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
            <Upload className="h-4 w-4 text-(--acc,#52A8EA)" />
            {stage === "complete" ? "Upload complete" : "Upload files"}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Select files and upload them to a folder in {courseCode}.
          </DialogDescription>
        </DialogHeader>

        <div className="flex max-h-[65vh] min-w-0 flex-col gap-4 overflow-y-auto px-5 py-4">
          <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="min-w-0">
              <p className="mb-1 font-mono text-[10px] tracking-wider text-(--tx-faint,#5C6976) uppercase">
                Course
              </p>
              <div className="truncate rounded-sm border border-(--line-soft,#1B2530) bg-(--bg-raise,#1C2833)/60 px-3 py-2 text-xs">
                {courseCode}
              </div>
            </div>
            <label className="min-w-0">
              <span className="mb-1 block font-mono text-[10px] tracking-wider text-(--tx-faint,#5C6976) uppercase">
                Destination folder
              </span>
              <select
                value={selectedCategory}
                disabled={
                  isDirectFolderUpload ||
                  stage === "uploading" ||
                  stage === "complete"
                }
                onChange={(event) => setCategoryOverride(event.target.value)}
                className="h-9 w-full min-w-0 rounded-sm border border-(--line,#25313E) bg-(--bg-raise,#1C2833) px-3 text-xs text-(--tx,#DCE3EA) outline-none focus-visible:ring-2 focus-visible:ring-(--acc,#52A8EA) disabled:opacity-60"
              >
                {categories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {(validationMessages.length > 0 || requestError) && (
            <div
              role="alert"
              className="rounded-sm border border-(--danger,#E0625C)/30 bg-(--danger,#E0625C)/10 px-3 py-2 text-xs text-(--danger-tx,#F0A19D)"
            >
              {requestError && <p className="font-semibold">{requestError}</p>}
              {validationMessages.length > 0 && (
                <ul className="space-y-1">
                  {validationMessages.map((message) => (
                    <li key={message} className="flex gap-2">
                      <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span className="min-w-0 break-words">{message}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {stage === "complete" ? (
            <div
              role="status"
              className="rounded-sm border border-(--ok,#4FB07C)/30 bg-(--ok,#4FB07C)/10 px-4 py-3"
            >
              <div className="flex items-center gap-2 text-sm font-semibold text-(--ok,#4FB07C)">
                <CheckCircle2 className="h-4 w-4" />
                {selectedFiles.length}{" "}
                {selectedFiles.length === 1 ? "file" : "files"} uploaded
              </div>
              <p className="mt-1 text-xs text-(--tx-dim,#8B98A7)">
                The files were added to {selectedCategory}. AI indexing
                continues in the background.
              </p>
            </div>
          ) : (
            <div
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ")
                  inputRef.current?.click()
              }}
              onDragEnter={(event) => {
                event.preventDefault()
                setIsDragging(true)
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-sm border-2 border-dashed p-6 text-center transition-colors outline-none focus-visible:ring-2 focus-visible:ring-(--acc,#52A8EA) ${isDragging ? "border-(--acc,#52A8EA) bg-(--acc,#52A8EA)/10" : "border-(--line,#25313E) bg-(--bg-raise,#1C2833)/30 hover:border-(--acc,#52A8EA)/70"}`}
            >
              <UploadCloud className="h-7 w-7 text-(--acc,#52A8EA)" />
              <span className="text-sm font-semibold">
                Drop files here or browse
              </span>
              <span className="font-mono text-[10px] text-(--tx-faint,#5C6976)">
                PDF, Markdown and DOCX · Maximum 50 MB per file
              </span>
              <input
                ref={inputRef}
                type="file"
                multiple
                className="sr-only"
                accept=".pdf,.md,.markdown,.doc,.docx"
                onChange={(event) =>
                  addFiles(Array.from(event.target.files ?? []))
                }
              />
            </div>
          )}

          {selectedFiles.length > 0 && (
            <div className="min-w-0">
              <div className="mb-2 flex items-center justify-between gap-3">
                <p className="font-mono text-[10px] tracking-wider text-(--tx-faint,#5C6976) uppercase">
                  Files ({selectedFiles.length})
                </p>
                <span className="font-mono text-[10px] text-(--tx-faint,#5C6976)">
                  {formatFileSize(totalSize)}
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                {selectedFiles.map((file) => (
                  <div
                    key={`${file.name}:${file.size}`}
                    className="flex min-w-0 items-center gap-2 rounded-sm border border-(--line-soft,#1B2530) bg-(--bg-raise,#1C2833)/50 px-3 py-2"
                  >
                    {stage === "uploading" ? (
                      <LoaderCircle className="h-4 w-4 shrink-0 animate-spin text-(--acc,#52A8EA)" />
                    ) : stage === "complete" ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-(--ok,#4FB07C)" />
                    ) : (
                      <FileText className="h-4 w-4 shrink-0 text-(--acc,#52A8EA)" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium">
                        {file.name}
                      </p>
                      <p className="font-mono text-[10px] text-(--tx-faint,#5C6976)">
                        {formatFileSize(file.size)} ·{" "}
                        {stage === "uploading"
                          ? "Uploading…"
                          : stage === "complete"
                            ? "Uploaded · Indexing"
                            : "Ready to upload"}
                      </p>
                    </div>
                    {stage === "selected" && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        aria-label={`Remove ${file.name}`}
                        onClick={() => removeFile(file)}
                      >
                        <Trash2 />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="grid grid-cols-2 border-t border-(--line-soft,#1B2530) px-5 py-3 sm:grid-cols-[auto_auto] sm:justify-end">
          {stage === "complete" ? (
            <Button
              type="button"
              size="sm"
              className="col-span-2 w-full sm:col-span-1 sm:w-auto"
              onClick={resetAndClose}
            >
              Done
            </Button>
          ) : (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={stage === "uploading"}
                onClick={resetAndClose}
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={selectedFiles.length === 0 || stage === "uploading"}
                onClick={handleUpload}
              >
                {stage === "uploading" ? (
                  <>
                    <LoaderCircle className="animate-spin" />
                    Uploading…
                  </>
                ) : (
                  <>
                    <Upload />
                    Upload {selectedFiles.length || ""}{" "}
                    {selectedFiles.length === 1 ? "file" : "files"}
                  </>
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
