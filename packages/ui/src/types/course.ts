import type { components } from "@workspace/contracts"

import type { ChatFile } from "../components/chat/Chat"

export interface Milestone {
  /** MILESTONE.id. Absent only on the old hand-written mock rows. */
  id?: string
  w: string
  n: string
  s: number // 1 = done, 0 = pending
  now?: boolean
  tag?: "exam" | "lab" | "project"
}

export interface MockCourse {
  id: string
  code: string
  name: string
  year: number
  semester: number
  description: string
  week: number
  weeks: number
  target: string
  roadmap: Milestone[]
}
export type FileStatus = components["schemas"]["FileRead"]["status"]

export interface MockDocumentFile extends ChatFile {
  totalPages: number
  uploadedAt: string
  size: string
  status?: FileStatus
  errorMessage?: string | null
  previewState?: "ready" | "loading" | "error" | "unsupported"
  previewError?: string | null
  contentByPage?: Record<number, string>
}
