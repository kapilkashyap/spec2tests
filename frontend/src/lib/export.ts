import * as XLSX from "xlsx";

import type { TestCase } from "./types";

/**
 * A single flattened row matching the POC blueprint's seven mandatory
 * table columns, in display order. Keys double as the header row when
 * passed through `XLSX.utils.json_to_sheet`.
 */
export interface TestCaseWorksheetRow {
  "Test Case ID": string;
  "Requirement Reference": string;
  "Test Scenario": string;
  "Pre-conditions": string;
  "Test Steps": string;
  "Expected Result": string;
  Priority: string;
}

/**
 * Flatten an array of {@link TestCase} objects into plain row objects whose
 * keys are the seven blueprint-mandated column headers, in order:
 * Test Case ID, Requirement Reference, Test Scenario, Pre-conditions,
 * Test Steps, Expected Result, Priority.
 *
 * Both {@link exportToExcel} and {@link exportToCSV} build their worksheet
 * from this single helper so the two export formats always share identical
 * column ordering, headers, and cell escaping (via SheetJS).
 */
export function buildWorksheetRows(testCases: TestCase[]): TestCaseWorksheetRow[] {
  return testCases.map((testCase) => ({
    "Test Case ID": testCase.id,
    "Requirement Reference": testCase.requirement_reference,
    "Test Scenario": testCase.title,
    "Pre-conditions": testCase.preconditions.join("; "),
    "Test Steps": testCase.steps.map((step, index) => `${index + 1}. ${step}`).join(" | "),
    "Expected Result": testCase.expected_result,
    Priority: testCase.priority,
  }));
}

/**
 * Trigger a browser download of an in-memory `Blob` by momentarily
 * attaching a hidden `<a download>` element to the DOM and programmatically
 * clicking it, then revoking the temporary object URL.
 *
 * Shared by {@link exportToCSV} and {@link exportToJSON} so the anchor-click
 * download mechanics are implemented in exactly one place.
 */
function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Export generated test cases as a real `.xlsx` workbook, entirely
 * client-side via SheetJS (`xlsx`). The single worksheet is named
 * "Test Cases" and its columns match the seven blueprint-mandated headers
 * produced by {@link buildWorksheetRows}.
 */
export function exportToExcel(testCases: TestCase[], filename = "test-cases.xlsx"): void {
  const worksheet = XLSX.utils.json_to_sheet(buildWorksheetRows(testCases));
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Test Cases");
  XLSX.writeFile(workbook, filename);
}

/**
 * Export generated test cases as CSV text, entirely client-side.
 *
 * Reuses the exact same `XLSX.utils.json_to_sheet(buildWorksheetRows(...))`
 * worksheet as {@link exportToExcel} and converts it with
 * `XLSX.utils.sheet_to_csv`, guaranteeing the CSV and Excel exports share
 * identical column ordering and cell escaping.
 */
export function exportToCSV(testCases: TestCase[], filename = "test-cases.csv"): void {
  const worksheet = XLSX.utils.json_to_sheet(buildWorksheetRows(testCases));
  const csvString = XLSX.utils.sheet_to_csv(worksheet);
  const blob = new Blob([csvString], { type: "text/csv;charset=utf-8;" });
  triggerBlobDownload(blob, filename);
}

/**
 * Export generated test cases as pretty-printed JSON, entirely client-side.
 *
 * Serializes the raw {@link TestCase} objects (not the flattened worksheet
 * rows) so the exported file is a faithful, lossless copy of the backend's
 * response payload.
 */
export function exportToJSON(testCases: TestCase[], filename = "test-cases.json"): void {
  const jsonString = JSON.stringify(testCases, null, 2);
  const blob = new Blob([jsonString], { type: "application/json" });
  triggerBlobDownload(blob, filename);
}
