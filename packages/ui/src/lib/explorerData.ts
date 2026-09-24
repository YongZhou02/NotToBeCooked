import type { CourseRead, FileRead, FolderRead } from "@workspace/contracts"

import type { MockCourse, MockDocumentFile } from "../types/course"

export function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`
  }

  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`
  }

  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

export function toUiCourse(course: CourseRead): MockCourse {
  return {
    id: course.id,
    code: course.code,
    name: course.name,
    year: course.year,
    semester: course.sem,
    description: "",
    week: 0,
    weeks: 0,
    target: "",
    roadmap: [],
  }
}

export function toUiFiles(
  files: FileRead[],
  folders: FolderRead[]
): MockDocumentFile[] {
  const folderNames = new Map(folders.map((folder) => [folder.id, folder.name]))

  return files.map((file) => ({
    id: file.id,
    name: file.filename,
    category: folderNames.get(file.folder_id) ?? "Unknown folder",
    totalPages: file.page_count ?? 1,
    uploadedAt: new Date(file.uploaded_at).toLocaleDateString(),
    size: formatFileSize(file.size_bytes),
    status: file.status,
    errorMessage: file.error_message,
    previewState:
      file.mime_type === "application/pdf" ? "ready" : "unsupported",
  }))
}
