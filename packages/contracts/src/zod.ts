import { makeApi, Zodios, type ZodiosOptions } from "@zodios/core";
import { z } from "zod";




const UserRead = z.object({ email: z.string().email(), display_name: z.union([z.string(), z.null()]).optional(), id: z.string().uuid(), created_at: z.string().datetime({ offset: true }) }).passthrough();
const ApiError = z.object({ code: z.string(), message: z.string() }).passthrough();
const TokenResponse = z.object({ access_token: z.string(), token_type: z.string().optional().default("bearer"), user: UserRead }).passthrough();
const LoginRequest = z.object({ email: z.string().email(), password: z.string().min(8) }).passthrough();
const ValidationError = z.object({ loc: z.array(z.union([z.string(), z.number()])), msg: z.string(), type: z.string(), input: z.unknown().optional(), ctx: z.object({}).partial().passthrough().optional() }).passthrough();
const HTTPValidationError = z.object({ detail: z.array(ValidationError) }).partial().passthrough();
const RegisterRequest = z.object({ display_name: z.string(), email: z.string().email(), password: z.string().min(8).regex(/.*[A-Z].*/) }).passthrough();
const Body_upload_file_files_post = z.object({ folder_id: z.string().uuid(), upload: z.string() }).passthrough();
const FileRead = z.object({ id: z.string().uuid(), folder_id: z.string().uuid(), filename: z.string(), storage_key: z.string(), sha256: z.union([z.string(), z.null()]).optional(), mime_type: z.string(), size_bytes: z.number().int(), page_count: z.union([z.number(), z.null()]).optional(), status: z.enum(["uploaded", "processing", "ready", "failed"]), error_message: z.union([z.string(), z.null()]).optional(), uploaded_at: z.string().datetime({ offset: true }), indexed_at: z.union([z.string(), z.null()]).optional() }).passthrough();
const IngestionResponse = z.object({ file_id: z.string().uuid(), ingestion_run_id: z.string().uuid(), status: z.enum(["queued", "processing", "ready", "failed"]), chunk_count: z.union([z.number(), z.null()]).optional(), error: z.union([z.string(), z.null()]).optional() }).passthrough();
const FileUpdate = z.object({ filename: z.union([z.string(), z.null()]), folder_id: z.union([z.string(), z.null()]) }).partial().passthrough();
const Body_replace_file_files__file_id__content_put = z.object({ upload: z.string() }).passthrough();
const RagQueryRequest = z.object({ question: z.string().min(1).max(2000), course_id: z.union([z.string(), z.null()]).optional(), conversation_id: z.union([z.string(), z.null()]).optional(), file_ids: z.union([z.array(z.string().uuid()), z.null()]).optional(), top_k: z.number().int().gte(1).lte(20).optional().default(5) });
const Citation = z.object({ marker: z.number().int().gte(1), file_id: z.string().uuid(), course_id: z.string().uuid(), filename: z.string().min(1), page: z.union([z.number(), z.null()]).optional(), page_end: z.union([z.number(), z.null()]).optional(), quote: z.string().min(1) });
const RagAnswer = z.object({ answer: z.string().min(1), citations: z.array(Citation).optional(), grounded: z.boolean(), uncovered: z.union([z.string(), z.null()]).optional(), used_chunks: z.number().int().gte(0), conversation_id: z.union([z.string(), z.null()]).optional() });
const course_id = z.union([z.string(), z.null()]).optional();
const Conversation = z.object({ id: z.union([z.string(), z.null()]).optional(), course_id: z.string().uuid(), title: z.string().optional().default("New Chat"), created_at: z.string().datetime({ offset: true }).optional(), updated_at: z.string().datetime({ offset: true }).optional() }).passthrough();
const ChatRole = z.enum(["user", "assistant"]);
const MessageRead = z.object({ id: z.string().uuid(), conversation_id: z.string().uuid(), scope_course_id: z.string().uuid(), role: ChatRole, content: z.string(), grounded: z.boolean(), uncovered: z.union([z.string(), z.null()]), citations: z.union([z.array(z.object({}).partial().passthrough()), z.null()]), mentioned_file_ids: z.union([z.array(z.string().uuid()), z.null()]), created_at: z.string().datetime({ offset: true }) }).passthrough();
const ConversationDetail = z.object({ id: z.string().uuid(), course_id: z.string().uuid(), title: z.string(), created_at: z.string().datetime({ offset: true }), updated_at: z.string().datetime({ offset: true }), messages: z.array(MessageRead).optional().default([]) }).passthrough();
const DeleteSessionResponse = z.object({ status: z.string().default("ok") }).partial().passthrough();
const IngestionRunStatus = z.enum(["queued", "processing", "ready", "failed"]);
const IngestionRunRead = z.object({ id: z.string().uuid(), file_id: z.string().uuid(), status: IngestionRunStatus, started_at: z.union([z.string(), z.null()]), completed_at: z.union([z.string(), z.null()]), error_message: z.union([z.string(), z.null()]) }).passthrough();
const CourseStatus = z.enum(["active", "archived"]);
const CourseRead = z.object({ id: z.string().uuid(), code: z.string(), name: z.string(), year: z.number().int(), sem: z.number().int(), status: CourseStatus, created_at: z.string().datetime({ offset: true }) }).passthrough();
const CourseCreate = z.object({ code: z.string(), name: z.string(), year: z.number().int(), sem: z.number().int() }).passthrough();
const CourseUpdate = z.object({ code: z.union([z.string(), z.null()]), name: z.union([z.string(), z.null()]), year: z.union([z.number(), z.null()]), sem: z.union([z.number(), z.null()]), status: z.union([CourseStatus, z.null()]) }).partial().passthrough();
const FolderCreate = z.object({ name: z.string(), parent_folder_id: z.union([z.string(), z.null()]).optional(), sort_order: z.number().int().optional().default(0) }).passthrough();
const FolderRead = z.object({ id: z.string().uuid(), course_id: z.string().uuid(), parent_folder_id: z.union([z.string(), z.null()]), name: z.string(), is_root: z.boolean(), sort_order: z.number().int(), created_at: z.string().datetime({ offset: true }) }).passthrough();
const FolderUpdate = z.object({ name: z.union([z.string(), z.null()]), sort_order: z.union([z.number(), z.null()]) }).partial().passthrough();

export const schemas = {
	UserRead,
	ApiError,
	TokenResponse,
	LoginRequest,
	ValidationError,
	HTTPValidationError,
	RegisterRequest,
	Body_upload_file_files_post,
	FileRead,
	IngestionResponse,
	FileUpdate,
	Body_replace_file_files__file_id__content_put,
	RagQueryRequest,
	Citation,
	RagAnswer,
	course_id,
	Conversation,
	ChatRole,
	MessageRead,
	ConversationDetail,
	DeleteSessionResponse,
	IngestionRunStatus,
	IngestionRunRead,
	CourseStatus,
	CourseRead,
	CourseCreate,
	CourseUpdate,
	FolderCreate,
	FolderRead,
	FolderUpdate,
};

const endpoints = makeApi([
	{
		method: "get",
		path: "/",
		alias: "read_root__get",
		requestFormat: "json",
		response: z.unknown(),
	},
	{
		method: "post",
		path: "/auth/login",
		alias: "login_auth_login_post",
		description: `Authenticates a user and returns a JWT access token.`,
		requestFormat: "json",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: LoginRequest
			},
		],
		response: TokenResponse,
		errors: [
			{
				status: 401,
				description: `Invalid email or password`,
				schema: ApiError
			},
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "post",
		path: "/auth/logout",
		alias: "logout_auth_logout_post",
		description: `Logs out the user by clearing the HttpOnly refresh token cookie.`,
		requestFormat: "json",
		response: z.unknown(),
	},
	{
		method: "get",
		path: "/auth/me",
		alias: "get_me_auth_me_get",
		description: `Returns the current logged-in user&#x27;s profile`,
		requestFormat: "json",
		response: UserRead,
		errors: [
			{
				status: 401,
				description: `Missing, invalid or expired access token`,
				schema: ApiError
			},
		]
	},
	{
		method: "post",
		path: "/auth/refresh",
		alias: "refresh_session_auth_refresh_post",
		description: `Refreshes an expired access token using HttpOnly refresh token cookie.`,
		requestFormat: "json",
		response: TokenResponse,
		errors: [
			{
				status: 401,
				description: `Invalid or expired refresh token`,
				schema: ApiError
			},
		]
	},
	{
		method: "post",
		path: "/auth/register",
		alias: "register_auth_register_post",
		description: `Registers a new user account.`,
		requestFormat: "json",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: RegisterRequest
			},
		],
		response: TokenResponse,
		errors: [
			{
				status: 400,
				description: `Email already exists`,
				schema: ApiError
			},
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "get",
		path: "/chat/sessions",
		alias: "get_sessions_chat_sessions_get",
		description: `Get any latest sessions or by course ID`,
		requestFormat: "json",
		parameters: [
			{
				name: "course_id",
				type: "Query",
				schema: course_id
			},
			{
				name: "limit",
				type: "Query",
				schema: z.number().int().gte(1).lte(100).optional().default(10)
			},
			{
				name: "offset",
				type: "Query",
				schema: z.number().int().gte(0).optional().default(0)
			},
		],
		response: z.array(Conversation),
		errors: [
			{
				status: 401,
				description: `Missing, invalid or expired access token`,
				schema: ApiError
			},
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "get",
		path: "/chat/sessions/:session_id",
		alias: "get_session_by_session_id_chat_sessions__session_id__get",
		description: `Get session messages`,
		requestFormat: "json",
		parameters: [
			{
				name: "session_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: ConversationDetail,
		errors: [
			{
				status: 401,
				description: `Missing, invalid or expired access token`,
				schema: ApiError
			},
			{
				status: 404,
				description: `Session not found`,
				schema: ApiError
			},
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "delete",
		path: "/chat/sessions/:session_id",
		alias: "delete_session_chat_sessions__session_id__delete",
		requestFormat: "json",
		parameters: [
			{
				name: "session_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: z.object({ status: z.string().default("ok") }).partial().passthrough(),
		errors: [
			{
				status: 401,
				description: `Missing, invalid or expired access token`,
				schema: ApiError
			},
			{
				status: 404,
				description: `Session not found`,
				schema: ApiError
			},
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "get",
		path: "/courses",
		alias: "list_courses_courses_get",
		requestFormat: "json",
		response: z.array(CourseRead),
	},
	{
		method: "post",
		path: "/courses",
		alias: "create_course_courses_post",
		requestFormat: "json",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: CourseCreate
			},
		],
		response: CourseRead,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "patch",
		path: "/courses/:course_id",
		alias: "update_course_courses__course_id__patch",
		requestFormat: "json",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: CourseUpdate
			},
			{
				name: "course_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: CourseRead,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "delete",
		path: "/courses/:course_id",
		alias: "delete_course_courses__course_id__delete",
		requestFormat: "json",
		parameters: [
			{
				name: "course_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: z.void(),
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "get",
		path: "/courses/:course_id/files",
		alias: "list_course_files_courses__course_id__files_get",
		requestFormat: "json",
		parameters: [
			{
				name: "course_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: z.array(FileRead),
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "post",
		path: "/courses/:course_id/folders",
		alias: "create_folder_courses__course_id__folders_post",
		requestFormat: "json",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: FolderCreate
			},
			{
				name: "course_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: FolderRead,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "get",
		path: "/courses/:course_id/folders",
		alias: "list_folders_courses__course_id__folders_get",
		requestFormat: "json",
		parameters: [
			{
				name: "course_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: z.array(FolderRead),
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "get",
		path: "/courses/:course_id/folders/:folder_id",
		alias: "get_folder_courses__course_id__folders__folder_id__get",
		requestFormat: "json",
		parameters: [
			{
				name: "course_id",
				type: "Path",
				schema: z.string().uuid()
			},
			{
				name: "folder_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: FolderRead,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "patch",
		path: "/courses/:course_id/folders/:folder_id",
		alias: "update_folder_courses__course_id__folders__folder_id__patch",
		requestFormat: "json",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: FolderUpdate
			},
			{
				name: "course_id",
				type: "Path",
				schema: z.string().uuid()
			},
			{
				name: "folder_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: FolderRead,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "delete",
		path: "/courses/:course_id/folders/:folder_id",
		alias: "delete_folder_courses__course_id__folders__folder_id__delete",
		requestFormat: "json",
		parameters: [
			{
				name: "course_id",
				type: "Path",
				schema: z.string().uuid()
			},
			{
				name: "folder_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: z.void(),
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "post",
		path: "/files",
		alias: "upload_file_files_post",
		description: `Store an uploaded file and record it. Does not index it.

Upload and ingestion are two endpoints on purpose, which is why &#x60;uploaded&#x60;
exists as a FileStatus value (restored 18 Aug). This one returns as soon as
the bytes are safe; &#x60;POST /files/{file_id}/ingest&#x60; is what turns them into
chunks.

&#x60;course_id&#x60; is read from the folder, never from the request. The client
could send one, and a client that sends the wrong one would be writing a row
that r42&#x27;s composite foreign key rejects -- so the correct value is already
known server-side, and asking for it only creates a way to be wrong.`,
		requestFormat: "form-data",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: Body_upload_file_files_post
			},
		],
		response: FileRead,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "patch",
		path: "/files/:file_id",
		alias: "update_file_files__file_id__patch",
		requestFormat: "json",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: FileUpdate
			},
			{
				name: "file_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: FileRead,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "delete",
		path: "/files/:file_id",
		alias: "delete_file_files__file_id__delete",
		requestFormat: "json",
		parameters: [
			{
				name: "file_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: z.void(),
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "get",
		path: "/files/:file_id/content",
		alias: "get_file_content_files__file_id__content_get",
		requestFormat: "json",
		parameters: [
			{
				name: "file_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: z.void(),
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "put",
		path: "/files/:file_id/content",
		alias: "replace_file_files__file_id__content_put",
		requestFormat: "form-data",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: z.object({ upload: z.string() }).passthrough()
			},
			{
				name: "file_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: FileRead,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "post",
		path: "/files/:file_id/ingest",
		alias: "ingest_file_files__file_id__ingest_post",
		requestFormat: "json",
		parameters: [
			{
				name: "file_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: IngestionResponse,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "get",
		path: "/health",
		alias: "health_check_health_get",
		requestFormat: "json",
		response: z.unknown(),
	},
	{
		method: "get",
		path: "/ingestion-runs/:ingestion_run_id",
		alias: "get_ingestion_run_ingestion_runs__ingestion_run_id__get",
		requestFormat: "json",
		parameters: [
			{
				name: "ingestion_run_id",
				type: "Path",
				schema: z.string().uuid()
			},
		],
		response: IngestionRunRead,
		errors: [
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
	{
		method: "post",
		path: "/rag/query",
		alias: "query_rag_query_post",
		requestFormat: "json",
		parameters: [
			{
				name: "body",
				type: "Body",
				schema: RagQueryRequest
			},
		],
		response: RagAnswer,
		errors: [
			{
				status: 401,
				description: `Missing, invalid or expired access token`,
				schema: ApiError
			},
			{
				status: 404,
				description: `Session or course not found`,
				schema: ApiError
			},
			{
				status: 422,
				description: `Validation Error`,
				schema: HTTPValidationError
			},
		]
	},
]);

export const api = new Zodios(endpoints);

export function createApiClient(baseUrl: string, options?: ZodiosOptions) {
    return new Zodios(baseUrl, endpoints, options);
}
