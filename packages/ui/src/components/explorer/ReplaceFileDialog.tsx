import { useState } from "react"
import { LoaderCircle } from "lucide-react"
import { Button } from "../button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../dialog"

export function ReplaceFileDialog({
  fileName,
  onOpenChange,
  onReplace,
}: {
  fileName: string
  onOpenChange: (open: boolean) => void
  onReplace: (file: File) => Promise<void>
}) {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const extension = fileName.includes(".")
    ? `.${fileName.split(".").pop()!.toLowerCase()}`
    : ""

  const submit = async () => {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      await onReplace(file)
      onOpenChange(false)
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Couldn’t replace the file. Please try again."
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !busy && onOpenChange(open)}>
      <DialogContent className="border-(--line,#25313E) bg-(--bg-panel,#121A23) text-(--tx,#DCE3EA) sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Replace file</DialogTitle>
          <DialogDescription className="break-words">
            Replace the contents of {fileName}. Its name and folder will stay
            the same. The current contents will be overwritten and the file will
            be reindexed. Previous chat answers will not be updated; ask again
            after indexing finishes.
          </DialogDescription>
        </DialogHeader>
        <label className="grid gap-2 text-sm">
          Choose a new {extension} file
          <input
            type="file"
            accept={extension || undefined}
            disabled={busy}
            className="w-full rounded border border-(--line,#25313E) p-2 text-xs"
            onChange={(event) => {
              const selected = event.target.files?.[0] ?? null
              if (
                selected &&
                (!extension || !selected.name.toLowerCase().endsWith(extension))
              ) {
                setFile(null)
                setError(
                  `Choose a ${extension} file to match the original format.`
                )
              } else {
                setFile(selected)
                setError(null)
              }
            }}
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-(--danger-tx,#F0A19D)">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button disabled={busy || !file} onClick={() => void submit()}>
            {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}
            {busy ? "Replacing…" : "Replace and reindex"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
