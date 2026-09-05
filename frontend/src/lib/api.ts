import type { ApiErrorResponse, TestCase } from "./types";

/**
 * Base URL of the Spec2Tests FastAPI backend.
 *
 * Configured via the `VITE_API_BASE_URL` environment variable (see
 * `frontend/.env.example`), falling back to the local backend dev server.
 */
const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

const GENERATE_TEST_CASES_PATH = "/api/generate-test-cases";

/** Parameters accepted by {@link generateTestCases}. */
export interface GenerateTestCasesParams {
  /** Mandatory Business Requirements Document (.pdf, .docx, or .txt). */
  brdFile: File;
  /** Optional Functional Requirements Document (.pdf, .docx, or .txt). */
  frdFile: File | null;
  /** Optional free-text additional context to include in the generation prompt. */
  context: string;
}

/**
 * Attempt to extract a human-readable error message from a failed response.
 *
 * Falls back to a generic message derived from the HTTP status if the body
 * is not valid JSON or does not match FastAPI's `{"detail": "..."}` shape.
 */
async function extractErrorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof (body as ApiErrorResponse).detail === "string"
    ) {
      return (body as ApiErrorResponse).detail;
    }
  } catch {
    // Response body was not JSON (or was empty) — fall through to the
    // generic status-based message below.
  }
  return `Request failed with status ${response.status} ${response.statusText}`.trim();
}

/**
 * Generate structured test cases from a mandatory BRD, an optional FRD, and
 * optional free-text context by calling `POST /api/generate-test-cases` on
 * the Spec2Tests backend.
 *
 * @param params.brdFile Mandatory Business Requirements Document.
 * @param params.frdFile Optional Functional Requirements Document.
 * @param params.context Optional free-text additional context.
 * @returns The raw JSON array of generated {@link TestCase} objects.
 * @throws Error with the backend's `detail` message (or a generic HTTP
 *   status message) if the request does not succeed, or a network error if
 *   the backend cannot be reached at all.
 */
export async function generateTestCases({
  brdFile,
  frdFile,
  context,
}: GenerateTestCasesParams): Promise<TestCase[]> {
  const formData = new FormData();
  // Field names must match the FastAPI endpoint's parameter names exactly:
  // see backend/app/routers/generate_test_cases.py.
  formData.append("brd_file", brdFile, brdFile.name);
  if (frdFile) {
    formData.append("frd_file", frdFile, frdFile.name);
  }
  if (context.trim().length > 0) {
    formData.append("context", context);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${GENERATE_TEST_CASES_PATH}`, {
      method: "POST",
      body: formData,
    });
  } catch (networkError) {
    const reason =
      networkError instanceof Error ? networkError.message : String(networkError);
    throw new Error(
      `Could not reach the Spec2Tests backend at ${API_BASE_URL}. ${reason}`
    );
  }

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(detail);
  }

  return (await response.json()) as TestCase[];
}
