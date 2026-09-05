import { RotateCcw } from "lucide-react";

import { ExportToolbar } from "@/components/ExportToolbar";
import { FileUploadPanel } from "@/components/FileUploadPanel";
import { StatusBanner } from "@/components/StatusBanner";
import { TestCaseTable } from "@/components/TestCaseTable";
import { Button } from "@/components/ui/button";
import { useTestCaseGeneration } from "@/hooks/useTestCaseGeneration";

/**
 * Root application shell.
 *
 * Wires the `useTestCaseGeneration` state machine to the upload/configuration
 * region (`FileUploadPanel` + `StatusBanner`) and the results region
 * (`ExportToolbar` + `TestCaseTable`), and hosts the top-level "Start Over"
 * action that resets the entire workflow back to its initial idle state.
 */
function App() {
  const generation = useTestCaseGeneration();
  const { status, testCases, errorMessage, reset } = generation;

  const canReset = status === "success" || status === "error";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
        <header className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Spec2Tests &mdash; AI Manual Test Case Generator
            </h1>
            <p className="max-w-2xl text-sm text-slate-600">
              Upload a mandatory Business Requirements Document (BRD) &mdash; and optionally a
              Functional Requirements Document (FRD) plus free-text context &mdash; to generate a
              structured, exportable set of manual test cases powered by Gemini.
            </p>
          </div>
          {canReset ? (
            <Button type="button" variant="outline" onClick={reset} className="shrink-0">
              <RotateCcw aria-hidden="true" />
              Start Over
            </Button>
          ) : null}
        </header>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-1">
            <FileUploadPanel generation={generation} />
            <StatusBanner
              status={status}
              errorMessage={errorMessage}
              testCaseCount={testCases.length}
            />
          </div>

          <div className="space-y-4 lg:col-span-2">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-lg font-semibold">Generated Test Cases</h2>
              <ExportToolbar testCases={testCases} />
            </div>
            <TestCaseTable testCases={testCases} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
