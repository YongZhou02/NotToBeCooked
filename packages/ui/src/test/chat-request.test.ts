import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { classifyChatRequest } from "../lib/chatRequest.ts"

describe("chat request classification", () => {
  it("treats a natural whole-file explanation as a document summary", () => {
    const result = classifyChatRequest(
      "Explain all the concepts in this file in layman terms"
    )
    assert.deepEqual(result, {
      intent: "document_summary",
      scopesCurrentDocument: true,
    })
  })

  it("recognizes a whole-file explanation without requiring this file wording", () => {
    const result = classifyChatRequest(
      "Explain all the concepts in laymen term"
    )
    assert.deepEqual(result, {
      intent: "document_summary",
      scopesCurrentDocument: true,
    })
  })

  it("scopes a normal question about this document without forcing summary mode", () => {
    const result = classifyChatRequest(
      "What does this document say about conflict?"
    )
    assert.equal(result.intent, "question")
    assert.equal(result.scopesCurrentDocument, true)
  })

  it("keeps an ordinary course question at course scope", () => {
    const result = classifyChatRequest("What is conflict?")
    assert.equal(result.scopesCurrentDocument, false)
  })

  it("keeps the Condense quick action as a document summary", () => {
    const result = classifyChatRequest("Condense")
    assert.equal(result.intent, "document_summary")
  })

  it("scopes every document quick action to the open file", () => {
    for (const prompt of ["Quiz me", "Simplify", "Storyboard"]) {
      const result = classifyChatRequest(prompt)
      assert.deepEqual(result, {
        intent: "document_summary",
        scopesCurrentDocument: true,
      })
    }
  })
})
