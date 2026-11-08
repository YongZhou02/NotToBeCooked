import type { ResolvedQuestion } from "./questions"

export interface EvidenceItem {
  groupId?: string
  documentId: string
  page: number
  quote: string
}

export function flattenEvidence(q: ResolvedQuestion): EvidenceItem[] {
  return q.evidence_groups.flatMap((g) =>
    (g.alternatives ?? []).map((alt) => ({
      groupId: g.id,
      documentId: alt.document_id,
      page: alt.pdf_page,
      quote: alt.quote,
    }))
  )
}
