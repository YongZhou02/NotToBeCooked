import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { splitInlineTokens } from "../lib/inlineTokens.ts"

const markers = (text: string) =>
  splitInlineTokens(text).filter((token) => /^\[\d+\]$/.test(token))

describe("citation markers in an answer", () => {
  it("renders a marker after a space or a full stop, or at the start", () => {
    assert.deepEqual(markers("[1] Light becomes energy [2]. Stored.[3]"), [
      "[1]",
      "[2]",
      "[3]",
    ])
  })

  it("leaves code indexing as text: arr[0], dp[i][2], f(x)[1]", () => {
    // Found in review 24 Nov 2026: the tokenizer cut `[0]` out of `arr[0]` as
    // a marker, and MarkdownContent draws every marker token as a citation pill.
    assert.deepEqual(
      markers(
        "After the loop arr[0] holds the minimum [1]. dp[i][2] and f(x)[3] cost [2]."
      ),
      ["[1]", "[2]"]
    )
  })

  it("keeps the indexed text intact", () => {
    assert.ok(splitInlineTokens("arr[0] is first").join("").includes("arr[0]"))
  })
})
