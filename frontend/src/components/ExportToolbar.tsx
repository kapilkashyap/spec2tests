import { FileJson, FileSpreadsheet, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { exportToCSV, exportToExcel, exportToJSON } from "@/lib/export";
import type { TestCase } from "@/lib/types";

/** Props accepted by {@link ExportToolbar}. */
export interface ExportToolbarProps {
  /** The currently generated test cases to export. */
  testCases: TestCase[];
}

/**
 * A row of export actions ("Export Excel", "Export CSV", "Export JSON")
 * for the currently generated test cases. Every export is fully
 * client-side (SheetJS for Excel/CSV, native `Blob` for JSON) — no
 * additional backend round-trips are made.
 *
 * All three buttons are disabled whenever there are no test cases to
 * export, so the toolbar is safe to render unconditionally alongside
 * {@link import("./TestCaseTable").TestCaseTable}.
 */
export function ExportToolbar({ testCases }: ExportToolbarProps): JSX.Element {
  const hasTestCases = testCases.length > 0;

  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Export test cases">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!hasTestCases}
        onClick={() => exportToExcel(testCases)}
      >
        <FileSpreadsheet aria-hidden="true" />
        Export Excel
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!hasTestCases}
        onClick={() => exportToCSV(testCases)}
      >
        <FileText aria-hidden="true" />
        Export CSV
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!hasTestCases}
        onClick={() => exportToJSON(testCases)}
      >
        <FileJson aria-hidden="true" />
        Export JSON
      </Button>
    </div>
  );
}
