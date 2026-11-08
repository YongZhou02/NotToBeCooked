import type { DashboardData } from "../types"

export interface SourceDocument {
  /** The document_id written into evidence. */
  id: string
  file: string
  label: string
  url: string
  pages?: number
}

/**
 * Ids that older exports and evaluation/datasets/cpt316/candidate_sources.json
 * already use for the four course PDFs. They only name a PDF that
 * dashboard_data.json does not list yet; a document the data does list always
 * keeps its own id.
 */
const LEGACY_IDS: Record<string, string> = {
  "cpt316_topic1_semantic_text_only.pdf": "topic1",
  "cpt316_topic2_lexical_semantic_text.pdf": "cpt316-topic2-lexical",
  "cpt316_topic3_updated_semantic_text.pdf": "cpt316-topic3-updated",
  "cpt316_topic3_student_semantic_text.pdf": "cpt316-topic3-student",
}

/** Other spellings of those ids that earlier dashboards accepted. */
const LEGACY_ALIASES: Record<string, string> = {
  "cpt316-topic1": "topic1",
  cpt316_topic1: "topic1",
  "cpt316 topic 1": "topic1",
  cpt316_topic1_semantic_text_only: "topic1",
  topic2: "cpt316-topic2-lexical",
  "cpt316-topic2": "cpt316-topic2-lexical",
  cpt316_topic2: "cpt316-topic2-lexical",
  "cpt316 topic 2": "cpt316-topic2-lexical",
  topic3: "cpt316-topic3-updated",
  "cpt316-topic3": "cpt316-topic3-updated",
  cpt316_topic3: "cpt316-topic3-updated",
  "cpt316-topic3-updated": "cpt316-topic3-updated",
  "cpt316 topic 3": "cpt316-topic3-updated",
  "cpt316-topic3-student": "cpt316-topic3-student",
}

export function documentUrl(file: string): string {
  return `${import.meta.env.BASE_URL}documents/${encodeURIComponent(file)}`
}

function baseName(path: string): string {
  return path.split(/[\\/]/).pop() ?? path
}

function slug(file: string): string {
  return file
    .replace(/\.pdf$/i, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
}

export function documentLabel(file: string): string {
  const topic = /topic\s*_?(\d+)/i.exec(file)
  if (!topic) return file.replace(/\.pdf$/i, "").replace(/_/g, " ")
  const variant = /updated/i.test(file)
    ? " (Updated)"
    : /student/i.test(file)
      ? " (Student)"
      : ""
  return `Topic ${topic[1]}${variant}`
}

/**
 * Every PDF the reader can show: first the ones dashboard_data.json lists
 * (with that id), then any other PDF found in the documents folder.
 */
export function buildRegistry(
  data: DashboardData,
  files: readonly string[]
): SourceDocument[] {
  const registry: SourceDocument[] = []
  const seen = new Set<string>()

  for (const doc of data.dataset.documents ?? []) {
    const file = baseName(doc.path)
    if (seen.has(file.toLowerCase())) continue
    seen.add(file.toLowerCase())
    registry.push({
      id: doc.id,
      file,
      label: documentLabel(file),
      url: documentUrl(file),
      pages: doc.pages,
    })
  }
  for (const file of files) {
    if (seen.has(file.toLowerCase())) continue
    seen.add(file.toLowerCase())
    registry.push({
      id: LEGACY_IDS[file.toLowerCase()] ?? slug(file),
      file,
      label: documentLabel(file),
      url: documentUrl(file),
    })
  }
  return registry
}

/**
 * The PDF an evidence quote's document_id (or a file name) points at. An id
 * nothing recognises falls back to the first PDF, as the old dashboard did.
 */
export function resolveDocument(
  registry: readonly SourceDocument[],
  idOrName: string | undefined | null
): SourceDocument | undefined {
  const fallback = registry[0]
  if (!idOrName) return fallback
  const clean = String(idOrName).trim()
  const lower = clean.toLowerCase()

  const byId = registry.find((doc) => doc.id === clean)
  if (byId) return byId
  const aliased = LEGACY_ALIASES[lower]
  if (aliased) {
    const target = registry.find((doc) => doc.id === aliased)
    if (target) return target
  }
  const byIdLoose = registry.find((doc) => doc.id.toLowerCase() === lower)
  if (byIdLoose) return byIdLoose
  const byFile = registry.find(
    (doc) =>
      doc.file.toLowerCase() === lower ||
      doc.file.toLowerCase() === `${lower}.pdf`
  )
  return byFile ?? fallback
}
