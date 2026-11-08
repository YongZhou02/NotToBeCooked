import fs from "node:fs"
import path from "node:path"
import type { Connect, Plugin } from "vite"

interface Options {
  /** evaluation/dashboard/dashboard_data.json */
  dataFile: string
  /** evaluation/datasets/cpt316/documents */
  documentsDir: string
}

const DATA_URL = "dashboard_data.json"
const DOCS_URL = "documents/"
const MANIFEST_URL = "documents/index.json"

function listPdfs(dir: string): string[] {
  try {
    return fs
      .readdirSync(dir)
      .filter((name) => name.toLowerCase().endsWith(".pdf"))
      .sort()
  } catch {
    return []
  }
}

/**
 * Serves the evaluation data and its source PDFs from where they already
 * live in the repository, in dev and in the build, so nothing is duplicated
 * into git:
 *
 *   dashboard_data.json     -> evaluation/dashboard/dashboard_data.json
 *   documents/<name>.pdf    -> evaluation/datasets/cpt316/documents/<name>.pdf
 *   documents/index.json    -> a list of the PDF file names in that folder
 *
 * The list lets the app offer every PDF in the folder even when the data
 * file has not been rebuilt to name them yet.
 */
export function evaluationAssets({ dataFile, documentsDir }: Options): Plugin {
  let base = "/"

  const handler: Connect.NextHandleFunction = (req, res, next) => {
    const pathname = decodeURIComponent((req.url ?? "").split("?")[0] ?? "")
    const relative = pathname.startsWith(base)
      ? pathname.slice(base.length)
      : pathname.replace(/^\//, "")

    if (relative === DATA_URL) {
      res.setHeader("Content-Type", "application/json")
      res.setHeader("Cache-Control", "no-cache")
      fs.createReadStream(dataFile)
        .on("error", () => {
          res.statusCode = 404
          res.end("dashboard_data.json not found")
        })
        .pipe(res)
      return
    }

    if (relative === MANIFEST_URL) {
      res.setHeader("Content-Type", "application/json")
      res.setHeader("Cache-Control", "no-cache")
      res.end(JSON.stringify(listPdfs(documentsDir)))
      return
    }

    if (
      relative.startsWith(DOCS_URL) &&
      relative.toLowerCase().endsWith(".pdf")
    ) {
      // Only a bare file name: nothing outside the documents folder is reachable.
      const name = relative.slice(DOCS_URL.length)
      const file = path.join(documentsDir, name)
      if (name !== path.basename(name) || !fs.existsSync(file)) {
        res.statusCode = 404
        res.end("Not found")
        return
      }
      res.setHeader("Content-Type", "application/pdf")
      res.setHeader("Cache-Control", "no-cache")
      fs.createReadStream(file).pipe(res)
      return
    }

    next()
  }

  return {
    name: "evaluation-assets",
    configResolved(config) {
      base = config.base.startsWith(".") ? "/" : config.base
    },
    configureServer(server) {
      server.middlewares.use(handler)
    },
    generateBundle() {
      this.emitFile({
        type: "asset",
        fileName: DATA_URL,
        source: fs.readFileSync(dataFile),
      })
      const pdfs = listPdfs(documentsDir)
      this.emitFile({
        type: "asset",
        fileName: MANIFEST_URL,
        source: JSON.stringify(pdfs),
      })
      for (const name of pdfs) {
        this.emitFile({
          type: "asset",
          fileName: DOCS_URL + name,
          source: fs.readFileSync(path.join(documentsDir, name)),
        })
      }
    },
  }
}
