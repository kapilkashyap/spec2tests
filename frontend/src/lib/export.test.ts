import { afterEach, describe, expect, it } from "vitest";

import { buildWorksheetRows, exportToCSV, exportToJSON } from "@/lib/export";
import type { TestCase } from "@/lib/types";

const SAMPLE_TEST_CASES: TestCase[] = [
  {
    id: "TC-001",
    requirement_reference: "BRD-1.1",
    title: "User can log in with valid credentials",
    description: "Verifies successful authentication with valid credentials.",
    preconditions: ["A registered user account exists."],
    steps: ["Navigate to the login page.", "Enter valid credentials.", "Submit the form."],
    expected_result: "The user is authenticated and redirected to the dashboard.",
    priority: "High",
    type: "Functional",
  },
  {
    id: "TC-002",
    requirement_reference: "",
    title: "User sees an error for an invalid password",
    description: "Verifies the system rejects an incorrect password with a clear error.",
    preconditions: [],
    steps: ["Navigate to the login page.", "Enter an incorrect password.", "Submit the form."],
    expected_result: "An inline error message is displayed and login is rejected.",
    priority: "Medium",
    type: "Negative",
  },
];

const EXPECTED_HEADER_KEYS = [
  "Test Case ID",
  "Requirement Reference",
  "Test Scenario",
  "Pre-conditions",
  "Test Steps",
  "Expected Result",
  "Priority",
];

const originalCreateObjectURL = URL.createObjectURL;
const originalRevokeObjectURL = URL.revokeObjectURL;
const originalAnchorClick = HTMLAnchorElement.prototype.click;

afterEach(() => {
  URL.createObjectURL = originalCreateObjectURL;
  URL.revokeObjectURL = originalRevokeObjectURL;
  HTMLAnchorElement.prototype.click = originalAnchorClick;
});

/**
 * Stub the browser download machinery used by `triggerBlobDownload`
 * (shared by `exportToCSV`/`exportToJSON`):
 *
 * - `URL.createObjectURL` is replaced with a spy that captures the real
 *   `Blob` it was called with (so tests can assert on its `type`/content)
 *   and returns a fake object URL.
 * - `HTMLAnchorElement.prototype.click` is stubbed to a no-op because
 *   jsdom does not implement page navigation, and clicking an anchor with
 *   a `blob:` href would otherwise log a harmless-but-noisy
 *   "Not implemented: navigation" console error.
 * - `URL.revokeObjectURL` is stubbed to a no-op since there is no real
 *   object URL registry to clean up in this test environment.
 */
function stubDownloadMachinery(): { getCapturedBlob: () => Blob | null } {
  let capturedBlob: Blob | null = null;
  URL.createObjectURL = (blob: Blob) => {
    capturedBlob = blob;
    return "blob:mock-url";
  };
  URL.revokeObjectURL = () => undefined;
  HTMLAnchorElement.prototype.click = () => undefined;
  return { getCapturedBlob: () => capturedBlob };
}

describe("buildWorksheetRows", () => {
  it("maps a sample TestCase[] to rows with the exact 7 expected header keys in order", () => {
    const rows = buildWorksheetRows(SAMPLE_TEST_CASES);

    expect(rows).toHaveLength(SAMPLE_TEST_CASES.length);
    for (const row of rows) {
      expect(Object.keys(row)).toEqual(EXPECTED_HEADER_KEYS);
    }

    const [firstRow] = rows;
    expect(firstRow["Test Case ID"]).toBe("TC-001");
    expect(firstRow["Requirement Reference"]).toBe("BRD-1.1");
    expect(firstRow["Test Scenario"]).toBe("User can log in with valid credentials");
    expect(firstRow["Pre-conditions"]).toBe("A registered user account exists.");
    expect(firstRow["Test Steps"]).toBe(
      "1. Navigate to the login page. | 2. Enter valid credentials. | 3. Submit the form."
    );
    expect(firstRow["Expected Result"]).toBe(
      "The user is authenticated and redirected to the dashboard."
    );
    expect(firstRow.Priority).toBe("High");
  });

  it("returns an empty array when given no test cases", () => {
    expect(buildWorksheetRows([])).toEqual([]);
  });
});

describe("exportToJSON", () => {
  it("produces a Blob of application/json MIME type", () => {
    const { getCapturedBlob } = stubDownloadMachinery();

    exportToJSON(SAMPLE_TEST_CASES, "test-cases.json");

    const capturedBlob = getCapturedBlob();
    expect(capturedBlob).not.toBeNull();
    expect(capturedBlob).toBeInstanceOf(Blob);
    expect((capturedBlob as Blob).type).toBe("application/json");
  });
});

describe("exportToCSV", () => {
  it("produces a Blob of text/csv MIME type", () => {
    const { getCapturedBlob } = stubDownloadMachinery();

    exportToCSV(SAMPLE_TEST_CASES, "test-cases.csv");

    const capturedBlob = getCapturedBlob();
    expect(capturedBlob).not.toBeNull();
    expect(capturedBlob).toBeInstanceOf(Blob);
    expect((capturedBlob as Blob).type).toContain("text/csv");
  });
});
