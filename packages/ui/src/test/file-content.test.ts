import { describe, it } from "node:test"
import assert from "node:assert/strict"
import {
  describeFileContentError,
  fileContentReducer,
  type FileContentState,
} from "../lib/fileContent.ts"

const idle: FileContentState = { status: "idle" }
const blobA = new Blob(["A"])
const blobB = new Blob(["B"])

describe("r78 · fetching a document's bytes", () => {
  it("goes idle -> loading -> ready", () => {
    const loading = fileContentReducer(idle, { type: "load", fileId: "a" })
    assert.deepEqual(loading, { status: "loading", fileId: "a" })

    const ready = fileContentReducer(loading, {
      type: "loaded",
      fileId: "a",
      blob: blobA,
    })
    assert.equal(ready.status, "ready")
    assert.equal(ready.status === "ready" && ready.blob, blobA)
  })

  it("drops an answer for a file nobody is waiting on", () => {
    // Open A, switch to B before A answers, then A answers. Without this guard
    // A's bytes render under B's filename.
    let state = fileContentReducer(idle, { type: "load", fileId: "a" })
    state = fileContentReducer(state, { type: "load", fileId: "b" })

    const stale = fileContentReducer(state, {
      type: "loaded",
      fileId: "a",
      blob: blobA,
    })
    assert.deepEqual(stale, { status: "loading", fileId: "b" })

    const fresh = fileContentReducer(stale, {
      type: "loaded",
      fileId: "b",
      blob: blobB,
    })
    assert.equal(fresh.status === "ready" && fresh.blob, blobB)
  })

  it("drops a stale failure too, so a dead tab cannot show an error in a live one", () => {
    let state = fileContentReducer(idle, { type: "load", fileId: "a" })
    state = fileContentReducer(state, { type: "load", fileId: "b" })

    const after = fileContentReducer(state, {
      type: "failed",
      fileId: "a",
      error: { code: "HTTP_ERROR", message: "File not found" },
    })
    assert.deepEqual(after, { status: "loading", fileId: "b" })
  })

  it("carries the API's own message through", () => {
    const loading = fileContentReducer(idle, { type: "load", fileId: "a" })
    const failed = fileContentReducer(loading, {
      type: "failed",
      fileId: "a",
      error: { code: "HTTP_ERROR", message: "File not found" },
    })
    assert.equal(
      failed.status === "error" && failed.message,
      "File not found"
    )
  })

  it("says something a person can act on when the request never left", () => {
    assert.match(
      describeFileContentError(new TypeError("Failed to fetch")),
      /connection/i
    )
  })

  it("never renders an empty error box", () => {
    assert.ok(describeFileContentError({}).length > 0)
    assert.ok(describeFileContentError(null).length > 0)
  })
})
