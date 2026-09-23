import {
  AlertTriangle,
  FolderOpen,
  FolderPlus,
  RefreshCw,
  SearchX,
} from "lucide-react"

import { Button } from "../button"

interface ExplorerLoadingStateProps {
  variant: "loading"
}

interface ExplorerEmptyStateProps {
  variant: "empty"
  folderName?: string
  onUpload?: () => void
  onCreateFolder?: () => void
}

interface ExplorerErrorStateProps {
  variant: "error"
  onRetry: () => void
}

interface ExplorerNoResultsStateProps {
  variant: "no-results"
  query: string
  onClear: () => void
}

type ExplorerStateProps =
  | ExplorerLoadingStateProps
  | ExplorerEmptyStateProps
  | ExplorerErrorStateProps
  | ExplorerNoResultsStateProps

export function ExplorerState(props: ExplorerStateProps) {
  if (props.variant === "loading") {
    return (
      <div
        role="status"
        aria-label="Loading folders and files"
        className="flex flex-col gap-3 px-1 py-2"
      >
        {Array.from({ length: 4 }, (_, index) => (
          <div
            key={index}
            className="flex animate-pulse flex-col gap-2 rounded-sm border border-(--line-soft,#1B2530) p-2"
          >
            <div className="h-3 w-2/3 rounded-sm bg-(--bg-hover,#213040)" />

            <div className="ml-4 h-8 rounded-sm bg-(--bg-raise,#1C2833)" />
            <div className="ml-4 h-8 rounded-sm bg-(--bg-raise,#1C2833)" />
          </div>
        ))}

        <span className="sr-only">Loading folders and files…</span>
      </div>
    )
  }

  if (props.variant === "error") {
    return (
      <div
        role="alert"
        className="flex flex-1 flex-col items-center justify-center px-5 text-center"
      >
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-sm border border-(--danger,#E0625C)/30 bg-(--danger,#E0625C)/10">
          <AlertTriangle className="h-5 w-5 text-(--danger-tx,#F0A19D)" />
        </div>

        <h2 className="text-sm font-semibold text-(--tx,#DCE3EA)">
          Couldn’t load your folders and files
        </h2>

        <p className="mt-1 max-w-52 text-xs leading-5 text-(--tx-dim,#8B98A7)">
          Check your connection and try again.
        </p>

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={props.onRetry}
        >
          <RefreshCw className="h-4 w-4" />
          Try again
        </Button>
      </div>
    )
  }

  if (props.variant === "no-results") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-5 text-center">
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-sm border border-(--line,#25313E) bg-(--bg-raise,#1C2833)">
          <SearchX className="h-5 w-5 text-(--tx-dim,#8B98A7)" />
        </div>

        <p className="text-sm font-semibold text-(--tx,#DCE3EA)">
          No matching files or folders
        </p>

        <p className="mt-1 max-w-52 text-xs leading-5 text-(--tx-dim,#8B98A7)">
          Nothing matched “{props.query}”. Try another search.
        </p>

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={props.onClear}
        >
          Clear search
        </Button>
      </div>
    )
  }
  return (
    <div className="flex flex-col items-center px-4 py-6 text-center">
      <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-sm border border-(--line,#25313E) bg-(--bg-raise,#1C2833)">
        <FolderOpen className="h-4 w-4 text-(--tx-dim,#8B98A7)" />
      </div>

      <p className="text-xs font-semibold text-(--tx,#DCE3EA)">
        {props.folderName ? "This folder is empty" : "No folders yet"}
      </p>

      {props.folderName && (
        <p
          title={props.folderName}
          className="mt-1 max-w-full truncate text-[11px] text-(--tx-faint,#5C6976)"
        >
          {props.folderName}
        </p>
      )}

      <p className="mt-1 text-[11px] leading-4 text-(--tx-dim,#8B98A7)">
        {props.folderName
          ? "Upload your first file to get started."
          : "Create a folder before uploading your first file."}
      </p>

      {props.onCreateFolder ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={props.onCreateFolder}
        >
          <FolderPlus className="h-4 w-4" />
          Create folder
        </Button>
      ) : props.onUpload ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={props.onUpload}
        >
          Upload here
        </Button>
      ) : null}
    </div>
  )
}
