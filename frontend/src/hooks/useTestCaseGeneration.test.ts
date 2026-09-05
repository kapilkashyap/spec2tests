import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { generateTestCases } from "@/lib/api";
import type { TestCase } from "@/lib/types";
import { BRD_MANDATORY_MESSAGE, useTestCaseGeneration } from "@/hooks/useTestCaseGeneration";

vi.mock("@/lib/api", () => ({
  generateTestCases: vi.fn(),
}));

const mockedGenerateTestCases = generateTestCases as unknown as ReturnType<typeof vi.fn>;

function makeFile(name: string, type = "application/pdf"): File {
  return new File(["dummy file contents"], name, { type });
}

const SAMPLE_TEST_CASES: TestCase[] = [
  {
    id: "TC-001",
    requirement_reference: "BRD-1.1",
    title: "User can log in with valid credentials",
    description: "Verifies successful authentication.",
    preconditions: ["A registered user account exists."],
    steps: ["Navigate to login page.", "Enter valid credentials.", "Submit."],
    expected_result: "The user is authenticated.",
    priority: "High",
    type: "Functional",
  },
];

describe("useTestCaseGeneration", () => {
  beforeEach(() => {
    mockedGenerateTestCases.mockReset();
  });

  it("blocks submit and surfaces the BRD-mandatory inline error when no BRD is selected", async () => {
    const { result } = renderHook(() => useTestCaseGeneration());

    expect(result.current.isBrdMissing).toBe(true);
    expect(result.current.status).toBe("idle");

    await act(async () => {
      await result.current.submit();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toBe(BRD_MANDATORY_MESSAGE);
    // The mocked API client must never be called when the client-side
    // BRD-mandatory rule blocks submission.
    expect(mockedGenerateTestCases).not.toHaveBeenCalled();
  });

  it("clears the missing-BRD error once a BRD file is selected via SET_BRD_FILE", async () => {
    const { result } = renderHook(() => useTestCaseGeneration());

    await act(async () => {
      await result.current.submit();
    });
    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toBe(BRD_MANDATORY_MESSAGE);

    act(() => {
      result.current.setBrdFile(makeFile("brd.pdf"));
    });

    expect(result.current.isBrdMissing).toBe(false);
    expect(result.current.status).toBe("idle");
    expect(result.current.errorMessage).toBeNull();
    expect(result.current.brdFile?.name).toBe("brd.pdf");
  });

  it("transitions idle -> submitting -> success on a successful submit()", async () => {
    let resolveGenerate: (value: TestCase[]) => void = () => {};
    mockedGenerateTestCases.mockImplementation(
      () =>
        new Promise<TestCase[]>((resolve) => {
          resolveGenerate = resolve;
        })
    );

    const { result } = renderHook(() => useTestCaseGeneration());

    act(() => {
      result.current.setBrdFile(makeFile("brd.pdf"));
    });
    expect(result.current.status).toBe("idle");

    let submitPromise: Promise<void>;
    act(() => {
      submitPromise = result.current.submit();
    });

    await waitFor(() => expect(result.current.status).toBe("submitting"));
    expect(result.current.testCases).toEqual([]);

    await act(async () => {
      resolveGenerate(SAMPLE_TEST_CASES);
      await submitPromise;
    });

    expect(result.current.status).toBe("success");
    expect(result.current.testCases).toEqual(SAMPLE_TEST_CASES);
    expect(result.current.errorMessage).toBeNull();
    expect(mockedGenerateTestCases).toHaveBeenCalledTimes(1);
    expect(mockedGenerateTestCases).toHaveBeenCalledWith({
      brdFile: result.current.brdFile,
      frdFile: null,
      context: "",
    });
  });

  it("transitions to error with the thrown message on a failed submit()", async () => {
    mockedGenerateTestCases.mockRejectedValueOnce(new Error("Backend returned 502 Bad Gateway"));

    const { result } = renderHook(() => useTestCaseGeneration());

    act(() => {
      result.current.setBrdFile(makeFile("brd.pdf"));
    });

    await act(async () => {
      await result.current.submit();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toBe("Backend returned 502 Bad Gateway");
    expect(result.current.testCases).toEqual([]);
  });
});
