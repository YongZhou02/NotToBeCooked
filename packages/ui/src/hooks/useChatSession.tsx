import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  api,
  type ConversationDetail,
  type MessageRead,
  type RagAnswer,
} from "@workspace/contracts"
import { useWorkspace, selectActiveCourse, ragScope } from "../store/workspace"
import {
  type ChatMessage,
  groupCitations,
} from "../components/chat/ChatMessage"
import { extractMentionsAndResolve, type FileItem } from "../lib/mentions"

export type FilesInput =
  | FileItem[]
  | Record<string, string | { id?: string; name: string }>
  | Map<string, string>

function normalizeFiles(input?: FilesInput): {
  fileList: FileItem[]
  lookupName: (id: string) => string | undefined
} {
  if (!input) {
    return { fileList: [], lookupName: () => undefined }
  }

  if (Array.isArray(input)) {
    const map = new Map<string, string>()
    for (const f of input) {
      if (f && f.id && f.name) map.set(f.id, f.name)
    }
    return {
      fileList: input,
      lookupName: (id: string) => map.get(id),
    }
  }

  if (input instanceof Map) {
    const list: FileItem[] = []
    for (const [id, name] of input.entries()) {
      list.push({ id, name })
    }
    return {
      fileList: list,
      lookupName: (id: string) => input.get(id),
    }
  }

  if (typeof input === "object" && input !== null) {
    const map = new Map<string, string>()
    const list: FileItem[] = []
    for (const [key, val] of Object.entries(input)) {
      if (typeof val === "string") {
        map.set(key, val)
        list.push({ id: key, name: val })
      } else if (val && typeof val === "object") {
        const fileId = val.id || key
        map.set(fileId, val.name)
        list.push({ id: fileId, name: val.name })
      }
    }
    return {
      fileList: list,
      lookupName: (id: string) => map.get(id),
    }
  }

  return { fileList: [], lookupName: () => undefined }
}

let tempIdSeq = 0
function createOptimisticUserMessage(
  conversationId: string,
  courseId: string | null,
  content: string,
  mentionedFileIds: string[] | null
): MessageRead {
  tempIdSeq += 1
  return {
    id: `temp-${tempIdSeq}`,
    conversation_id: conversationId,
    scope_course_id: courseId ?? "",
    role: "user",
    content,
    grounded: false,
    // A user's own turn has no coverage claim to make -- `uncovered` is what the
    // assistant says the sources did not answer (r47).
    uncovered: null,
    citations: null,
    mentioned_file_ids: mentionedFileIds,
    created_at: new Date().toISOString(),
  }
}

export interface SendMessageInput {
  text: string
  fileIds?: string[]
  intent?: "question" | "document_summary"
}

interface MutationContext {
  previousDetail?: ConversationDetail
  conversationId: string | null
}

export const useChatSession = (courseId: string | null, files?: FilesInput) => {
  const queryClient = useQueryClient()
  const { fileList, lookupName } = normalizeFiles(files)

  const activeCourseWorkspace = useWorkspace(selectActiveCourse)
  const activeConversationId =
    activeCourseWorkspace?.activeConversationId ?? null
  const setActiveConversation = useWorkspace(
    (state) => state.setActiveConversation
  )

  // Fetch all sessions for this course
  const sessionsQuery = useQuery({
    queryKey: ["chat", "sessions", courseId],
    queryFn: () => api.chat.sessions(courseId ?? undefined),
    enabled: !!courseId,
  })

  // Fetch active conversation messages
  const activeSessionQuery = useQuery({
    queryKey: ["chat", "session", activeConversationId],
    queryFn: () => api.chat.messages(activeConversationId!),
    enabled: !!activeConversationId,
  })

  // Send a message /rag/query with optimistic cache update
  const sendMessageMutation = useMutation<
    RagAnswer,
    Error,
    SendMessageInput,
    MutationContext
  >({
    mutationFn: async ({ text, fileIds, intent }: SendMessageInput) => {
      const scope = ragScope(useWorkspace.getState())
      // Parse @[Filename] mentions from text and resolve to file_ids
      const mentionResult = extractMentionsAndResolve(text, fileList)
      const effectiveFileIds =
        fileIds ?? mentionResult.fileIds ?? scope.file_ids ?? null

      return api.chat.query({
        question: mentionResult.cleanQuestion || text,
        course_id: scope.course_id ?? null,
        conversation_id: activeConversationId,
        file_ids: effectiveFileIds,
        top_k: 5,
        intent: intent ?? "question",
      })
    },
    onMutate: async ({ text, fileIds }: SendMessageInput) => {
      const scope = ragScope(useWorkspace.getState())
      const mentionResult = extractMentionsAndResolve(text, fileList)
      const effectiveFileIds =
        fileIds ?? mentionResult.fileIds ?? scope.file_ids ?? null
      const currentConvId = activeConversationId

      if (currentConvId) {
        // Cancel any outgoing refetches so they don't overwrite optimistic turn
        await queryClient.cancelQueries({
          queryKey: ["chat", "session", currentConvId],
        })

        // Snapshot previous ConversationDetail
        const previousDetail = queryClient.getQueryData<ConversationDetail>([
          "chat",
          "session",
          currentConvId,
        ])

        const optimisticMessage = createOptimisticUserMessage(
          currentConvId,
          courseId,
          text,
          effectiveFileIds
        )

        queryClient.setQueryData<ConversationDetail>(
          ["chat", "session", currentConvId],
          (old) => {
            if (!old) {
              return {
                id: currentConvId,
                course_id: courseId ?? "",
                title: "Chat",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                messages: [optimisticMessage],
              }
            }
            return {
              ...old,
              messages: [...old.messages, optimisticMessage],
            }
          }
        )

        return { previousDetail, conversationId: currentConvId }
      }

      return { previousDetail: undefined, conversationId: null }
    },
    onError: (_err, _input, context) => {
      if (context?.conversationId && context.previousDetail) {
        queryClient.setQueryData(
          ["chat", "session", context.conversationId],
          context.previousDetail
        )
      }
    },
    onSuccess: (data, _input, context) => {
      // If turn 1 created a new session, update activeConversationId in Zustand
      const newConversationId =
        (data as { conversation_id?: string; id?: string })?.conversation_id ??
        (data as { conversation_id?: string; id?: string })?.id

      if (!activeConversationId && newConversationId && courseId) {
        setActiveConversation(courseId, newConversationId)
      }

      // Ensure session list is refreshed
      queryClient.invalidateQueries({
        queryKey: ["chat", "sessions", courseId],
      })

      // Ensure messages for current conversation are refreshed
      const targetId =
        activeConversationId || newConversationId || context?.conversationId
      if (targetId) {
        queryClient.invalidateQueries({
          queryKey: ["chat", "session", targetId],
        })
      }
    },
  })

  // Delete session
  const deleteSessionMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      return api.chat.delete_session(sessionId!)
    },
    onSuccess: (_data, deletedSessionId) => {
      queryClient.invalidateQueries({
        queryKey: ["chat", "sessions", courseId],
      })
      if (activeConversationId === deletedSessionId && courseId) {
        setActiveConversation(courseId, null)
      }
    },
  })

  // Map server messages to ChatMessage format with filename lookup
  const messages: ChatMessage[] = (activeSessionQuery.data?.messages ?? []).map(
    (msgRead) => ({
      id: msgRead.id,
      role: msgRead.role as "user" | "assistant",
      content: msgRead.content,
      isOptimistic: msgRead.id.startsWith("temp-"),
      status: msgRead.id.startsWith("temp-") ? "pending" : "sent",
      citations: groupCitations(
        msgRead.citations as Array<Record<string, unknown>> | null | undefined,
        lookupName
      ),
    })
  )

  return {
    // Data
    sessions: (sessionsQuery.data ?? []).map((s) => ({
      id: s.id ?? "",
      title: s.title ?? "Untitled Chat",
      courseId: s.course_id,
      createdAt: s.created_at,
      updatedAt: s.updated_at,
    })),
    messages,
    activeConversationId,

    // Loading states
    isLoadingSessions: sessionsQuery.isLoading,
    isLoadingMessages: activeSessionQuery.isLoading,
    isSending: sendMessageMutation.isPending,

    // Actions
    sendMessage: (text: string, options?: Omit<SendMessageInput, "text">) =>
      sendMessageMutation.mutateAsync({
        text,
        ...options,
      }),
    deleteSession: (sessionId: string) =>
      deleteSessionMutation.mutateAsync(sessionId),
    selectSession: (sessionId: string | null) => {
      if (courseId) setActiveConversation(courseId, sessionId)
    },
    startNewChat: () => {
      if (courseId) setActiveConversation(courseId, null)
    },
  }
}
