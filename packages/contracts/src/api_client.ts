import {
    type LoginRequest,
    type RegisterRequest,
    type TokenResponse,
    type UserRead,
    type CourseRead,
    type FolderRead,
    type FolderCreate,
    type FolderUpdate,
    type FileRead,
    type FileUpdate,
    type IngestionResponse,
    type ApiError,
    type HTTPValidationError,
    type ValidationIssue,
    schemas,
    type Conversation,
    type ConversationDetail,
    type RagAnswer,
    type RagQueryRequest,
} from "./index.js"

/**
 * What `ApiClient` throws. Always an `ApiError`; `detail` is present only when
 * the backend rejected the request shape (FastAPI 422), so a form can map each
 * issue back onto the input that caused it.
 */
export interface ApiClientError extends ApiError {
    detail?: ValidationIssue[]
}

/** Narrow an unknown caught value to what this client throws. */
export function isApiClientError(e: unknown): e is ApiClientError {
    return (
        typeof e === "object" &&
        e !== null &&
        typeof (e as ApiError).code === "string" &&
        typeof (e as ApiError).message === "string"
    )
}

export interface ApiClientConfig {
    baseUrl?: string
    getToken?: () => string | null
    onUnauthorized?: () => void
    onTokenRefreshed?: (newToken: string, user: UserRead) => void
}

type RefreshSubscriber = (err?: unknown) => void

export class ApiClient {
    private baseUrl: string
    private getToken: () => string | null
    private onUnauthorized?: () => void
    private onTokenRefreshed?: (newToken: string, user: UserRead) => void

    // Race-condition control variables
    private isRefreshing: boolean = false
    private refreshSubscribers: RefreshSubscriber[] = []

    constructor(config: ApiClientConfig = {}) {
        this.baseUrl = config.baseUrl || this.resolveBaseUrl()
        // No storage fallback on purpose. The access token lives in memory only
        // (AuthContext holds it and calls setTokenGetter); the HttpOnly refresh
        // cookie is what survives a reload. Reading it back from localStorage
        // would put it somewhere any injected script can reach.
        this.getToken = config.getToken || (() => null)
        this.onUnauthorized = config.onUnauthorized
        this.onTokenRefreshed = config.onTokenRefreshed
    }

    public setTokenGetter(fn: () => string | null) {
        this.getToken = fn
    }

    public setOnUnauthorized(fn: () => void) {
        this.onUnauthorized = fn
    }

    public setOnTokenRefreshed(fn: (newToken: string, user: UserRead) => void) {
        this.onTokenRefreshed = fn
    }

    private subscribeRefresh(cb: RefreshSubscriber) {
        this.refreshSubscribers.push(cb)
    }

    private onRefreshSubscribers(err?: any) {
        this.refreshSubscribers.forEach((cb) => cb(err))
        this.refreshSubscribers = []
    }

    private resolveBaseUrl(): string {
        const env = (
            import.meta as ImportMeta & {
                env?: { VITE_API_URL?: string }
            }
        ).env

        return env?.VITE_API_URL || "http://localhost:8000"
    }

        private async request<T>(
        endpoint: string,
        options: RequestInit & {
            parseAs?: "json" | "blob" | "none"
        } = {}
    ): Promise<T> {
        // `parseAs` is ours, not fetch's, so it is taken out before the rest of
        // `options` is spread into the request. It survives the 401 retry below
        // because that path passes the original `options` through unchanged.
        const { parseAs = "json", ...init } = options
        const token = this.getToken()

const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData

        const headers: Record<string, string> = {
            ...((init.headers as Record<string, string>) || {}),
        }

        if (!isFormData && !headers["Content-Type"]) {
            headers["Content-Type"] = "application/json"
        }

        if (token) {
            headers["Authorization"] = `Bearer ${token}`
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            ...init,
            credentials: "include",
            headers,
        })

        if (
            response.status === 401 &&
            endpoint !== "/auth/login" &&
            endpoint !== "/auth/refresh"
        ) {
            if (!this.isRefreshing) {
                this.isRefreshing = true

                try {
                    const refreshResult = await this.auth.refresh()
                    this.isRefreshing = false
                    this.onTokenRefreshed?.(
                        refreshResult.access_token,
                        refreshResult.user
                    )
                    this.onRefreshSubscribers()
                    return this.request<T>(endpoint, options)
                } catch (refreshErr: any) {
                    this.isRefreshing = false
                    this.onRefreshSubscribers(refreshErr)
                    this.onUnauthorized?.()
                    throw refreshErr
                }
            }

            return new Promise<T>((resolve, reject) => {
                this.subscribeRefresh((err) => {
                    if (err) {
                        reject(err)
                        return
                    }
                    this.request<T>(endpoint, options).then(resolve).catch(reject)
                })
            })
        }

        if (!response.ok) {
            let errorData: ApiClientError
            try {
                const rawJson = await response.json()
                const parsed = schemas.ApiError.safeParse(rawJson)
                if (parsed.success) {
                    errorData = parsed.data
                } else {
                    // FastAPI's 422 body is {detail: [{loc, msg, type}, ...]}. Keeping the
                    // issues in their own field is what lets a form map them back onto
                    // individual inputs; folding them into `message` stringifies an array.
                    const detail: unknown = (rawJson as HTTPValidationError | undefined)
                        ?.detail
                    if (Array.isArray(detail)) {
                        errorData = {
                            code: "VALIDATION_ERROR",
                            message: "Some fields are invalid",
                            detail,
                        }
                    } else if (typeof detail === "string") {
                        errorData = { code: "HTTP_ERROR", message: detail }
                    } else {
                        const nested = (detail as ApiError | undefined)?.message
                        errorData = {
                            code: "HTTP_ERROR",
                            message: nested ?? response.statusText,
                        }
                    }
                }
            } catch {
                errorData = { code: "UNKNOWN_ERROR", message: response.statusText }
            }
            throw errorData
        }

        // A blob response has no JSON to parse and `response.json()` would throw
        // on it. Everything above this line -- the token, the 401 refresh, the
        // error shapes -- is shared, which is the reason this is a parameter
        // rather than a second method.
        if (parseAs === "blob") {
            return response.blob() as Promise<T>
        }

        if (parseAs === "none") {
            return undefined as T
        }

        return response.json()
    }

    // Course Endpoints
    public courses = {
        list: (): Promise<CourseRead[]> =>
            this.request<CourseRead[]>("/courses", {
                method: "GET",
            }),
    }

    // Folder Endpoints
    public folders = {
        list: (courseId: string): Promise<FolderRead[]> =>
            this.request<FolderRead[]>(
                `/courses/${encodeURIComponent(courseId)}/folders`,
                {
                    method: "GET",
                }
            ),

        create: (
            courseId: string,
            data: FolderCreate
        ): Promise<FolderRead> =>
            this.request<FolderRead>(
                `/courses/${encodeURIComponent(courseId)}/folders`,
                {
                    method: "POST",
                    body: JSON.stringify(data),
                }
            ),

        update: (
            courseId: string,
            folderId: string,
            data: FolderUpdate
        ): Promise<FolderRead> =>
            this.request<FolderRead>(
                `/courses/${encodeURIComponent(courseId)}/folders/${encodeURIComponent(folderId)}`,
                {
                    method: "PATCH",
                    body: JSON.stringify(data),
                }
            ),

        delete: (
            courseId: string,
            folderId: string
        ): Promise<void> =>
            this.request<void>(
                `/courses/${encodeURIComponent(courseId)}/folders/${encodeURIComponent(folderId)}`,
                {
                    method: "DELETE",
                    parseAs: "none",
                }
            ),
    }

    // File Endpoints
    public files = {
        upload: (folderId: string, file: File): Promise<FileRead> => {
        const formData = new FormData()
        formData.append("folder_id", folderId)
        formData.append("upload", file)

        return this.request<FileRead>("/files", {
            method: "POST",
            body: formData,
        })
    },

        list: (courseId: string): Promise<FileRead[]> =>
            this.request<FileRead[]>(
                `/courses/${encodeURIComponent(courseId)}/files`,
                {
                    method: "GET",
                },
            ),

        update: (
            fileId: string,
            data: FileUpdate
        ): Promise<FileRead> =>
            this.request<FileRead>(
                `/files/${encodeURIComponent(fileId)}`,
                {
                    method: "PATCH",
                    body: JSON.stringify(data),
                }
            ),

        delete: (fileId: string): Promise<void> =>
            this.request<void>(
                `/files/${encodeURIComponent(fileId)}`,
                {
                    method: "DELETE",
                    parseAs: "none",
                }
            ),

        ingest: (fileId: string): Promise<IngestionResponse> =>
            this.request<IngestionResponse>(
                `/files/${encodeURIComponent(fileId)}/ingest`,
                {
                    method: "POST",
                }
            ),
        /**
         * The stored bytes of one file, as a Blob.
         *
         * `GET /files/{file_id}/content` answers with a FileResponse carrying
         * the file's own mime type, not JSON -- so this is the one call that
         * asks for `parseAs: "blob"`. Ownership is checked server-side and a
         * file the caller does not own comes back as 404, never 403: a 403
         * would answer "does this id exist", which is not a question a stranger
         * should get an answer to.
         *
         * The caller owns the Blob. Turning it into an object URL means
         * revoking that URL when the view goes away, or the bytes stay in
         * memory for the life of the tab -- `useFileContent` does that.
         */
        content: (fileId: string): Promise<Blob> =>
            this.request<Blob>(
                `/files/${encodeURIComponent(fileId)}/content`,
                { parseAs: "blob" }
            ),
    }

    // Auth Endpoints
    public auth = {
        login: (credentials: LoginRequest): Promise<TokenResponse> => {
            return this.request<TokenResponse>("/auth/login", {
                method: "POST",
                body: JSON.stringify(credentials),
            })
        },

        register: (data: RegisterRequest): Promise<TokenResponse> => {
            return this.request<TokenResponse>("/auth/register", {
                method: "POST",
                body: JSON.stringify(data),
            })
        },

        refresh: (): Promise<TokenResponse> => {
            return this.request<TokenResponse>("/auth/refresh", {
                method: "POST",
            })
        },

        logout: (): Promise<{ status: string }> => {
            return this.request<{ status: string }>("/auth/logout", {
                method: "POST",
            })
        },
    }

    public chat = {
        // get a list of Conversation via course_id
        sessions: (
            course_id?: string,
            offset: number = 0,
            limit: number = 10
        ): Promise<Conversation[]> => {
            const searchParams = new URLSearchParams({
                offset: offset.toString(),
                limit: limit.toString()
            })

            if (course_id) {
                searchParams.set("course_id", course_id)
            }

            return this.request<Conversation[]>(`/chat/sessions?${searchParams.toString()}`, {
                method: "GET"
            })
        },

        // get ConversationDetail via session_id
        messages: (session_id: string): Promise<ConversationDetail> => {
            return this.request<ConversationDetail>(`/chat/sessions/${session_id}`, {
                method: "GET"
            })
        },

        delete_session: (session_id: string): Promise<{ status: "ok" }> => {
            return this.request<{ status: "ok" }>(`/chat/sessions/${session_id}`, {
                method: "DELETE"
            })
        },

        query: (payload: RagQueryRequest): Promise<RagAnswer> => {
            return this.request<RagAnswer>("/rag/query", {
                method: "POST",
                body: JSON.stringify(payload)
            })
        }
    }
}

export const api = new ApiClient()
