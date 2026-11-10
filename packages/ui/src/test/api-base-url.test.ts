import assert from "node:assert/strict"
import { describe, it } from "node:test"
import { resolveApiBaseUrl } from "../../../contracts/src/api-base-url.ts"

describe("local API cookie site", () => {
  it("uses the numeric loopback host when the page uses it", () => {
    assert.equal(
      resolveApiBaseUrl("http://localhost:8000", "http://127.0.0.1:5173"),
      "http://127.0.0.1:8000"
    )
  })
  it("uses localhost when the page uses it, preserving the API path and port", () => {
    assert.equal(
      resolveApiBaseUrl("http://127.0.0.1:8001/api", "http://localhost:5173"),
      "http://localhost:8001/api"
    )
  })
  it("also aligns the default local API", () => {
    assert.equal(
      resolveApiBaseUrl(undefined, "http://127.0.0.1:5173"),
      "http://127.0.0.1:8000"
    )
  })
  it("preserves production, relative, and non-browser configuration", () => {
    for (const [api, page] of [
      ["https://example.com/api", "http://127.0.0.1:5173"],
      ["/api", "https://example.com"],
      ["http://localhost:8000", "https://example.com"],
      ["http://localhost:8000", undefined],
      ["http://localhost:8000", "https://localhost:5173"],
    ]) {
      assert.equal(resolveApiBaseUrl(api, page), api)
    }
  })
})
