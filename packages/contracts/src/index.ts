import type { components, paths } from "./schema.js";

export { schemas } from "./zod.js";
export { ApiClient, api, isApiClientError } from "./api_client.js";
export type { ApiClientError } from "./api_client.js";

// Helper type exports for clean imports in frontend apps
export type UserRead = components["schemas"]["UserRead"];

export type CourseRead = components["schemas"]["CourseRead"];
export type FolderRead = components["schemas"]["FolderRead"];
export type FolderCreate =
    components["schemas"]["FolderCreate"];
export type FolderUpdate =
    components["schemas"]["FolderUpdate"];
export type FileRead = components["schemas"]["FileRead"];
export type FileUpdate = components["schemas"]["FileUpdate"];
export type IngestionResponse =
    components["schemas"]["IngestionResponse"];

export type LoginRequest = components["schemas"]["LoginRequest"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type ApiError = components["schemas"]["ApiError"];
export type HTTPValidationError = components["schemas"]["HTTPValidationError"];
/** One entry of a FastAPI 422 body: which field failed and why. */
export type ValidationIssue = components["schemas"]["ValidationError"];
export type Conversation = components["schemas"]["Conversation"];
export type ConversationDetail = components["schemas"]["ConversationDetail"];
export type MessageRead = components["schemas"]["MessageRead"]
export type RagAnswer = components["schemas"]["RagAnswer"]
export type RagQueryRequest = components["schemas"]["RagQueryRequest"]

export type { components, paths };
