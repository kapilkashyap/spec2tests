import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { GenerationState } from "@/hooks/useTestCaseGeneration";

export interface StatusBannerProps {
  /** Current generation status. */
  status: GenerationState["status"];
  /** Error message to display when `status === "error"`. */
  errorMessage: string | null;
  /** Number of test cases generated, used for the success message. */
  testCaseCount: number;
}

/**
 * Surfaces the current lifecycle status of the test case generation
 * workflow: a loading indicator while submitting, a destructive alert on
 * failure, and a success confirmation once test cases are returned. Renders
 * nothing while idle.
 */
export function StatusBanner({ status, errorMessage, testCaseCount }: StatusBannerProps) {
  if (status === "idle") {
    return null;
  }

  if (status === "submitting") {
    return (
      <Alert variant="default" role="status">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        <AlertTitle>Generating test cases&hellip;</AlertTitle>
        <AlertDescription>
          Extracting your documents and querying the AI model. This may take a moment.
        </AlertDescription>
      </Alert>
    );
  }

  if (status === "error") {
    return (
      <Alert variant="destructive" role="alert">
        <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        <AlertTitle>Generation failed</AlertTitle>
        <AlertDescription>
          {errorMessage ?? "An unexpected error occurred while generating test cases."}
        </AlertDescription>
      </Alert>
    );
  }

  // status === "success"
  return (
    <Alert variant="success" role="status">
      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
      <AlertTitle>Success</AlertTitle>
      <AlertDescription>
        Generated {testCaseCount} test case{testCaseCount === 1 ? "" : "s"}.
      </AlertDescription>
    </Alert>
  );
}
