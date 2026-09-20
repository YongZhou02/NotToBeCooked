/**
 * The state of fetching one file's bytes, kept out of React so it can be tested
 * without a DOM -- Gantt r78.
 *
 * The part worth having on its own is the race guard. A reader with tabs lets
 * someone open file A, switch to B before A answers, and the two responses then
 * arrive in whatever order the network chose. Without the fileId check below,
 * A's bytes land in B's tab: the wrong document under the right filename, which
 * is indistinguishable from a bug in the backend.
 */

export type FileContentState =
  | { status: "idle" }
  | { status: "loading"; fileId: string }
  | { status: "ready"; fileId: string; blob: Blob }
  | { status: "error"; fileId: string; message: string }

export type FileContentAction =
  | { type: "load"; fileId: string }
  | { type: "loaded"; fileId: string; blob: Blob }
  | { type: "failed"; fileId: string; error: unknown }
  | { type: "reset" }

/** 404 is also the answer for a file that exists and belongs to someone else --
 * the API never returns 403, because a 403 would confirm the id exists. So this
 * message has to be true of both cases. */
export function describeFileContentError(error: unknown): string {
  const code = (error as { code?: unknown } | null)?.code
  if (code === "HTTP_ERROR" || code === "NOT_FOUND") {
    const message = (error as { message?: unknown }).message
    if (typeof message === "string" && message.length > 0) return message
  }
  if (error instanceof TypeError) {
    return "Could not reach the server. Check your connection and try again."
  }
  const message = (error as { message?: unknown } | null)?.message
  return typeof message === "string" && message.length > 0
    ? message
    : "This document could not be opened."
}

export function fileContentReducer(
  state: FileContentState,
  action: FileContentAction
): FileContentState {
  switch (action.type) {
    case "load":
      return { status: "loading", fileId: action.fileId }
    case "loaded":
      // Answers for a file nobody is waiting on any more are dropped, not
      // rendered. See the note at the top.
      return state.status === "loading" && state.fileId === action.fileId
        ? { status: "ready", fileId: action.fileId, blob: action.blob }
        : state
    case "failed":
      return state.status === "loading" && state.fileId === action.fileId
        ? {
            status: "error",
            fileId: action.fileId,
            message: describeFileContentError(action.error),
          }
        : state
    case "reset":
      return { status: "idle" }
  }
}
