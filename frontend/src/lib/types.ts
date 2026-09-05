/**
 * Frontend/backend contract types.
 *
 * These mirror `backend/app/models/generation.py::TestCase` exactly (field
 * names, casing, and allowed enum values) so that responses from
 * `POST /api/generate-test-cases` can be consumed without any transformation.
 */

/** Relative importance of a generated test case. Matches `TestCasePriority` (Python enum). */
export type TestCasePriority = "High" | "Medium" | "Low";

/** Category describing the nature/intent of a generated test case. Matches `TestCaseType` (Python enum). */
export type TestCaseType =
  | "Functional"
  | "Negative"
  | "Edge Case"
  | "Integration"
  | "Boundary"
  | "Security"
  | "Performance"
  | "Usability";

/**
 * A single, structured test case derived from a specification document.
 *
 * Mirrors `backend/app/models/generation.py::TestCase`. The seven POC-mandated
 * table columns (Test Case ID, Requirement Reference, Test Scenario,
 * Pre-conditions, Test Steps, Expected Result, Priority) map to `id`,
 * `requirement_reference`, `title`, `preconditions`, `steps`,
 * `expected_result`, and `priority` respectively.
 */
export interface TestCase {
  /** Stable identifier for the test case (e.g. "TC-001"). */
  id: string;
  /**
   * Identifier/reference to the specific BRD/FRD requirement this test case
   * verifies (e.g. "BRD-3.2" or "REQ-014"). Defaults to an empty string when
   * the model cannot determine a specific reference.
   */
  requirement_reference: string;
  /** Short, descriptive test case title — rendered as the "Test Scenario" column. */
  title: string;
  /** Summary of what the test case verifies and why. */
  description: string;
  /** Conditions or setup required before executing the test steps. */
  preconditions: string[];
  /** Ordered list of actions to execute the test. */
  steps: string[];
  /** The expected outcome after performing the steps. */
  expected_result: string;
  /** Relative importance of this test case. */
  priority: TestCasePriority;
  /** Category describing the test case's intent. */
  type: TestCaseType;
}

/** Client-side lifecycle status for the test case generation workflow. */
export type GenerationStatus = "idle" | "submitting" | "success" | "error";

/** Shape of FastAPI's `HTTPException` JSON error body, e.g. `{"detail": "..."}`. */
export interface ApiErrorResponse {
  detail: string;
}
