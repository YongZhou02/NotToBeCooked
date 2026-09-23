import {
  AlertCircle,
  Download,
  FileQuestion,
  LoaderCircle,
  RotateCcw,
} from "lucide-react"

import { Button } from "../button"

type DocumentContentStateProps =
  | { variant: "loading"; fileName: string }
  | {
      variant: "error"
      fileName: string
      message?: string
      onRetry: () => void
    }
  | {
      variant: "unsupported"
      fileName: string
      isDownloading?: boolean
      downloadError?: string | null
      onDownload: () => void
    }

export function DocumentContentState(props: DocumentContentStateProps) {
  if (props.variant === "loading") {
    return (
      <div
        role="status"
        aria-label={`Loading ${props.fileName}`}
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5"
      >
        <div className="flex items-center gap-2 text-sm text-(--tx-dim,#8B98A7)">
          <LoaderCircle className="h-4 w-4 animate-spin text-(--acc,#52A8EA)" />
          Loading document…
        </div>
        <div className="flex flex-1 flex-col gap-5 rounded-sm border border-(--line-soft,#1B2530) bg-(--bg-raise,#1C2833)/35 p-8">
          <div className="h-3 w-2/5 animate-pulse rounded bg-(--line,#25313E)" />
          <div className="h-7 w-3/4 animate-pulse rounded bg-(--line,#25313E)" />
          <div className="space-y-3 pt-4">
            <div className="h-3 w-full animate-pulse rounded bg-(--line,#25313E)" />
            <div className="h-3 w-11/12 animate-pulse rounded bg-(--line,#25313E)" />
            <div className="h-3 w-4/5 animate-pulse rounded bg-(--line,#25313E)" />
          </div>
        </div>
      </div>
    )
  }

  if (props.variant === "error") {
    return (
      <div className="m-auto flex max-w-sm flex-col items-center gap-4 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-sm border border-(--danger,#E0625C)/30 bg-(--danger,#E0625C)/10">
          <AlertCircle className="h-5 w-5 text-(--danger-tx,#F0A19D)" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-(--tx,#DCE3EA)">
            Couldn’t load this document
          </h2>
          <p className="mt-1 text-sm leading-6 text-(--tx-dim,#8B98A7)">
            {props.message ??
              "Check your connection and try loading the original file again."}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={props.onRetry}
        >
          <RotateCcw />
          Try again
        </Button>
      </div>
    )
  }

  return (
    <div className="m-auto flex max-w-sm flex-col items-center gap-4 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-sm border border-(--line,#25313E) bg-(--bg-raise,#1C2833)">
        <FileQuestion className="h-5 w-5 text-(--tx-dim,#8B98A7)" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-(--tx,#DCE3EA)">
          Preview isn’t available
        </h2>
        <p className="mt-1 text-sm leading-6 text-(--tx-dim,#8B98A7)">
          NotToBeCooked can’t preview this file type yet. The original file is
          unchanged.
        </p>
      </div>
      {props.downloadError && (
        <p role="alert" className="text-sm text-(--danger-tx,#F0A19D)">
          {props.downloadError}
        </p>
      )}
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={props.isDownloading}
        onClick={props.onDownload}
      >
        {props.isDownloading ? (
          <LoaderCircle className="animate-spin" />
        ) : (
          <Download />
        )}
        {props.isDownloading ? "Downloading…" : "Download original"}
      </Button>
    </div>
  )
}
