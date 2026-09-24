import { useQuery } from "@tanstack/react-query"
import { api } from "@workspace/contracts"

export function useExplorerData(courseId: string | null) {
  const coursesQuery = useQuery({
    queryKey: ["courses"],
    queryFn: () => api.courses.list(),
  })

  const foldersQuery = useQuery({
    queryKey: ["courses", courseId, "folders"],
    queryFn: () => {
      if (!courseId) {
        throw new Error("A course must be selected before loading folders")
      }

      return api.folders.list(courseId)
    },
    enabled: Boolean(courseId),
  })

  const filesQuery = useQuery({
    queryKey: ["courses", courseId, "files"],
    queryFn: () => {
      if (!courseId) {
        throw new Error("A course must be selected before loading files")
      }

      return api.files.list(courseId)
    },
    enabled: Boolean(courseId),
    refetchInterval: (query) => {
      const files = query.state.data
      const hasPendingFile = files?.some(
        (file) => file.status === "uploaded" || file.status === "processing"
      )

      return hasPendingFile ? 3000 : false
    },
  })

  return {
    coursesQuery,
    foldersQuery,
    filesQuery,
  }
}
