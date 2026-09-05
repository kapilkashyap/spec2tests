import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TestCaseTable } from "@/components/TestCaseTable";
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
    requirement_reference: "BRD-2.3",
    title: "User sees an error for an invalid password",
    description: "Verifies the system rejects an incorrect password with a clear error.",
    preconditions: ["A registered user account exists."],
    steps: ["Navigate to the login page.", "Enter an incorrect password.", "Submit the form."],
    expected_result: "An inline error message is displayed and login is rejected.",
    priority: "Medium",
    type: "Negative",
  },
];

const EXPECTED_COLUMN_HEADERS = [
  "Test Case ID",
  "Requirement Reference",
  "Test Scenario",
  "Pre-conditions",
  "Test Steps",
  "Expected Result",
  "Priority",
];

describe("TestCaseTable", () => {
  it("renders all 7 required column headers", () => {
    render(<TestCaseTable testCases={SAMPLE_TEST_CASES} />);

    for (const header of EXPECTED_COLUMN_HEADERS) {
      expect(screen.getByRole("columnheader", { name: header })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("columnheader")).toHaveLength(EXPECTED_COLUMN_HEADERS.length);
  });

  it("renders one row per supplied test case with correct id/requirement_reference/title cell content", () => {
    render(<TestCaseTable testCases={SAMPLE_TEST_CASES} />);

    // Header row + one row per test case.
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(SAMPLE_TEST_CASES.length + 1);

    for (const testCase of SAMPLE_TEST_CASES) {
      expect(screen.getByText(testCase.id)).toBeInTheDocument();
      expect(screen.getByText(testCase.requirement_reference)).toBeInTheDocument();
      expect(screen.getByText(testCase.title)).toBeInTheDocument();
    }
  });

  it("renders the empty-state message when given an empty array", () => {
    render(<TestCaseTable testCases={[]} />);

    expect(
      screen.getByText(/no test cases yet.*upload a brd and click generate/i)
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
