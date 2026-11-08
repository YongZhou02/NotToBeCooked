import { execFileSync } from "node:child_process"
import crypto from "node:crypto"
import fs from "node:fs"
import path from "node:path"
import type { Connect } from "vite"

/**
 * Saves each person's question edits to evaluation/datasets/cpt316/team/<name>.json,
 * the same file merge_team_questions.py reads, so an edit is in git as soon as
 * it is made instead of living only in one browser.
 *
 *   GET /api/annotations  -> { reviewer, file, etag, content }
 *   PUT /api/annotations  <- { etag, content }  -> { etag } | 409 | 400
 *
 * Safety rules:
 * - Atomic: the new text goes to a temp file, is flushed to disk, then renamed
 *   over the old file. A crash leaves the old file or the new one, never half.
 * - No lost updates: every save names the etag (a hash of the file) it was
 *   based on. If the file changed since, by another tab or by hand, the save
 *   is refused with 409 and nothing is written.
 * - Valid: a save with a missing or repeated question id is refused with 400.
 * - One at a time: the check and the write run synchronously, so two saves
 *   can never interleave in this single-threaded server.
 */

const URL_PATH = "/api/annotations"
const MAX_BODY = 20 * 1024 * 1024

export function slug(name: string): string {
  return name
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

function reviewerName(repoRoot: string): string {
  const fromEnv = slug(process.env.EVAL_REVIEWER ?? "")
  if (fromEnv) return fromEnv
  try {
    const name = execFileSync("git", ["config", "user.name"], {
      cwd: repoRoot,
      encoding: "utf8",
    })
    return slug(name.split(/\s+/)[0] ?? "") || "reviewer"
  } catch {
    return "reviewer"
  }
}

export const etagOf = (text: string | null) =>
  text === null
    ? "none"
    : crypto.createHash("sha256").update(text).digest("hex").slice(0, 16)

function readText(file: string): string | null {
  try {
    return fs.readFileSync(file, "utf8")
  } catch {
    return null
  }
}

function sleepSync(ms: number) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms)
}

export function atomicWrite(file: string, text: string) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  const tmp = `${file}.${process.pid}.${Date.now()}.tmp`
  try {
    const fd = fs.openSync(tmp, "w")
    try {
      fs.writeSync(fd, text)
      fs.fsyncSync(fd)
    } finally {
      fs.closeSync(fd)
    }
    // Windows refuses a rename while another program briefly holds the file
    // (an editor, a virus scanner), so try a few times before giving up.
    for (let attempt = 0; ; attempt++) {
      try {
        fs.renameSync(tmp, file)
        return
      } catch (error) {
        const code = (error as NodeJS.ErrnoException).code
        if (attempt >= 8 || (code !== "EPERM" && code !== "EBUSY")) throw error
        sleepSync(50 * (attempt + 1))
      }
    }
  } finally {
    if (fs.existsSync(tmp)) fs.rmSync(tmp, { force: true })
  }
}

/** Returns the reason the content is bad, or null. */
export function validate(content: unknown): string | null {
  const file = content as { questions?: unknown } | null
  if (!file || typeof file !== "object" || !Array.isArray(file.questions))
    return "expected an object with a 'questions' list"
  const seen = new Set<string>()
  for (const row of file.questions as Record<string, unknown>[]) {
    const id = row?.id
    if (typeof id !== "string" || !id.trim()) return "a question has no id"
    if (seen.has(id)) return `question id ${id} appears twice`
    seen.add(id)
    if (typeof row.question !== "string") return `${id} has no question text`
  }
  return null
}

function send(
  res: Parameters<Connect.NextHandleFunction>[1],
  status: number,
  body: unknown
) {
  res.statusCode = status
  res.setHeader("Content-Type", "application/json")
  res.setHeader("Cache-Control", "no-store")
  res.end(JSON.stringify(body))
}

export function annotationsHandler({
  teamDir,
  repoRoot,
}: {
  teamDir: string
  repoRoot: string
}): Connect.NextHandleFunction {
  const reviewer = reviewerName(repoRoot)
  const file = path.join(teamDir, `${reviewer}.json`)
  const shown = path.relative(repoRoot, file).split(path.sep).join("/")

  return (req, res, next) => {
    const pathname = (req.url ?? "").split("?")[0]
    if (pathname !== URL_PATH) return next()

    if (req.method === "GET") {
      const text = readText(file)
      let content: unknown = null
      if (text !== null) {
        try {
          content = JSON.parse(text)
        } catch (error) {
          return send(res, 500, {
            error: `${shown} is not valid JSON, fix it by hand: ${String(error)}`,
          })
        }
      }
      return send(res, 200, {
        reviewer,
        file: shown,
        etag: etagOf(text),
        content,
      })
    }

    if (req.method !== "PUT") return send(res, 405, { error: "use GET or PUT" })

    const chunks: Buffer[] = []
    let size = 0
    req.on("data", (chunk: Buffer) => {
      size += chunk.length
      if (size <= MAX_BODY) chunks.push(chunk)
    })
    req.on("end", () => {
      if (size > MAX_BODY) return send(res, 413, { error: "save is too large" })
      let body: { etag?: string; content?: unknown }
      try {
        body = JSON.parse(Buffer.concat(chunks).toString("utf8"))
      } catch {
        return send(res, 400, { error: "body is not JSON" })
      }
      const problem = validate(body.content)
      if (problem) return send(res, 400, { error: problem })

      // From here to the write is synchronous: nothing can run in between.
      const current = etagOf(readText(file))
      if (body.etag !== current)
        return send(res, 409, {
          error: `${shown} changed outside this tab. Reload the page to load the latest version.`,
          etag: current,
        })
      const text = JSON.stringify(body.content, null, 2) + "\n"
      try {
        atomicWrite(file, text)
      } catch (error) {
        return send(res, 500, {
          error: `could not write ${shown}: ${String(error)}`,
        })
      }
      send(res, 200, { etag: etagOf(text), file: shown })
    })
  }
}
