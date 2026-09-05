import { useCallback, useReducer } from "react";

import { generateTestCases } from "@/lib/api";
import type { GenerationStatus, TestCase } from "@/lib/types";

/**
 * File extensions accepted for both the BRD and FRD uploads, matching the
 * backend's supported document-extraction formats
 * (`app.services.extraction.extract_document`).
 */
const SUPPORTED_FILE_EXTENSIONS = [".pdf", ".docx", ".txt"] as const;

/**
 * Mirrors `BRD_MANDATORY_MESSAGE` in
 * `backend/app/routers/generate_test_cases.py` so the client-side and
 * server-side error copy stay in sync.
 */
export const BRD_MANDATORY_MESSAGE =
  "BRD file is mandatory. Please upload a Business Requirements Document " +
  "(.pdf, .docx, or .txt) to generate test cases.";

/** Full client-side state for the test case generation workflow. */
export interface GenerationState {
  brdFile: File | null;
  frdFile: File | null;
  context: string;
  status: GenerationStatus;
  testCases: TestCase[];
  errorMessage: string | null;
}

const initialState: GenerationState = {
  brdFile: null,
  frdFile: null,
  context: "",
  status: "idle",
  testCases: [],
  errorMessage: null,
};

type GenerationAction =
  | { type: "SET_BRD_FILE"; file: File | null; error: string | null }
  | { type: "SET_FRD_FILE"; file: File | null; error: string | null }
  | { type: "CLEAR_FRD_FILE" }
  | { type: "SET_CONTEXT"; context: string }
  | { type: "SUBMIT_START" }
  | { type: "SUBMIT_SUCCESS"; testCases: TestCase[] }
  | { type: "SUBMIT_ERROR"; message: string }
  | { type: "RESET" };

function reducer(state: GenerationState, action: GenerationAction): GenerationState {
  switch (action.type) {
    case "SET_BRD_FILE":
      return {
        ...state,
        brdFile: action.error ? null : action.file,
        // Selecting a (valid) new BRD file clears any stale error/success
        // state so the user can immediately retry.
        status: action.error ? "error" : "idle",
        errorMessage: action.error,
        testCases: action.error ? state.testCases : [],
      };
    case "SET_FRD_FILE":
      return {
        ...state,
        frdFile: action.error ? null : action.file,
        status: action.error ? "error" : state.status === "error" ? "idle" : state.status,
        errorMessage: action.error ?? (state.status === "error" ? null : state.errorMessage),
      };
    case "CLEAR_FRD_FILE":
      return { ...state, frdFile: null };
    case "SET_CONTEXT":
      return { ...state, context: action.context };
    case "SUBMIT_START":
      return { ...state, status: "submitting", errorMessage: null };
    case "SUBMIT_SUCCESS":
      return { ...state, status: "success", testCases: action.testCases, errorMessage: null };
    case "SUBMIT_ERROR":
      return { ...state, status: "error", errorMessage: action.message, testCases: [] };
    case "RESET":
      return initialState;
    default:
      return state;
  }
}

/**
 * Validate that `file` has one of the extensions supported by the backend's
 * document extraction pipeline.
 *
 * @param file The selected file to validate.
 * @param role Human-readable role label ("BRD" or "FRD") used in the
 *   returned error message.
 * @returns A human-readable error message if the file type is unsupported,
 *   or `null` if the file is valid.
 */
export function validateFile(file: File, role: "BRD" | "FRD"): string | null {
  const lowerName = file.name.toLowerCase();
  const hasSupportedExtension = SUPPORTED_FILE_EXTENSIONS.some((extension) =>
    lowerName.endsWith(extension)
  );
  if (!hasSupportedExtension) {
    return `Unsupported ${role} file type. Please upload a ${SUPPORTED_FILE_EXTENSIONS.join(
      ", "
    )} file.`;
  }
  return null;
}

/** Return value of {@link useTestCaseGeneration}. */
export interface UseTestCaseGenerationResult extends GenerationState {
  /** `true` when no BRD file has been selected yet. */
  isBrdMissing: boolean;
  /** Select (or clear) the mandatory BRD file, validating its extension. */
  setBrdFile: (file: File | null) => void;
  /** Select (or clear) the optional FRD file, validating its extension. */
  setFrdFile: (file: File | null) => void;
  /** Remove the currently selected FRD file without validation. */
  clearFrdFile: () => void;
  /** Update the free-text additional context. */
  setContext: (context: string) => void;
  /** Submit the current BRD/FRD/context to the backend for generation. */
  submit: () => Promise<void>;
  /** Reset the entire workflow back to its initial idle state. */
  reset: () => void;
}

/**
 * `useReducer`-based state machine driving the test case generation
 * workflow: file selection, client-side validation, submission to the
 * backend, and the resulting idle/submitting/success/error lifecycle.
 *
 * The mandatory-BRD business rule is enforced here (mirroring the backend's
 * own validation in `generate_test_cases.py`) so the UI can give instant
 * feedback without a round-trip, while the backend remains the source of
 * truth if this check is ever bypassed (e.g. a stale client build).
 */
export function useTestCaseGeneration(): UseTestCaseGenerationResult {
  const [state, dispatch] = useReducer(reducer, initialState);

  const setBrdFile = useCallback((file: File | null) => {
    const error = file ? validateFile(file, "BRD") : null;
    dispatch({ type: "SET_BRD_FILE", file, error });
  }, []);

  const setFrdFile = useCallback((file: File | null) => {
    const error = file ? validateFile(file, "FRD") : null;
    dispatch({ type: "SET_FRD_FILE", file, error });
  }, []);

  const clearFrdFile = useCallback(() => {
    dispatch({ type: "CLEAR_FRD_FILE" });
  }, []);

  const setContext = useCallback((context: string) => {
    dispatch({ type: "SET_CONTEXT", context });
  }, []);

  const reset = useCallback(() => {
    dispatch({ type: "RESET" });
  }, []);

  const submit = useCallback(async () => {
    if (state.brdFile === null) {
      dispatch({ type: "SUBMIT_ERROR", message: BRD_MANDATORY_MESSAGE });
      return;
    }

    dispatch({ type: "SUBMIT_START" });
    try {
      const testCases = await generateTestCases({
        brdFile: state.brdFile,
        frdFile: state.frdFile,
        context: state.context,
      });
      dispatch({ type: "SUBMIT_SUCCESS", testCases });
    } catch (error) {
      const message = error instanceof Error ? error.message : "An unknown error occurred.";
      dispatch({ type: "SUBMIT_ERROR", message });
    }
  }, [state.brdFile, state.frdFile, state.context]);

  return {
    ...state,
    isBrdMissing: state.brdFile === null,
    setBrdFile,
    setFrdFile,
    clearFrdFile,
    setContext,
    submit,
    reset,
  };
}
