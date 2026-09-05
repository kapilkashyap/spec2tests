import { useRef } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { FileText, Loader2, UploadCloud, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { BRD_MANDATORY_MESSAGE, type UseTestCaseGenerationResult } from "@/hooks/useTestCaseGeneration";
import { cn } from "@/lib/utils";

/** File types accepted by both the BRD and FRD file inputs. */
const ACCEPTED_FILE_TYPES = ".pdf,.docx,.txt";

export interface FileUploadPanelProps {
  /** The full state + actions returned by `useTestCaseGeneration()`. */
  generation: UseTestCaseGenerationResult;
}

/**
 * Render a removable "chip" showing the name of a selected file.
 */
function SelectedFileChip({
  file,
  onRemove,
  disabled,
}: {
  file: File;
  onRemove: () => void;
  disabled: boolean;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-input bg-muted px-3 py-1.5 text-sm">
      <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="max-w-[220px] truncate" title={file.name}>
        {file.name}
      </span>
      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        aria-label={`Remove ${file.name}`}
        className="ml-1 rounded-full p-0.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50"
      >
        <X className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

/**
 * Card-wrapped upload form for the mandatory BRD, optional FRD, and optional
 * free-text context, plus the primary "Generate Test Cases" submit action.
 *
 * The BRD input is visually marked as required (asterisk + helper text) and
 * the submit button is disabled whenever no BRD is selected or a request is
 * already in flight, mirroring the backend's BRD-mandatory business rule.
 */
export function FileUploadPanel({ generation }: FileUploadPanelProps) {
  const {
    brdFile,
    frdFile,
    context,
    status,
    errorMessage,
    isBrdMissing,
    setBrdFile,
    setFrdFile,
    clearFrdFile,
    setContext,
    submit,
  } = generation;

  const brdInputRef = useRef<HTMLInputElement>(null);
  const frdInputRef = useRef<HTMLInputElement>(null);

  const isSubmitting = status === "submitting";
  // Only surface the inline BRD error once the user has actually attempted a
  // submission without a BRD file selected (i.e. the hook produced the
  // BRD-mandatory error message), rather than on first render.
  const showBrdInlineError = status === "error" && isBrdMissing && Boolean(errorMessage);

  const handleBrdChange = (event: ChangeEvent<HTMLInputElement>) => {
    setBrdFile(event.target.files?.[0] ?? null);
  };

  const handleFrdChange = (event: ChangeEvent<HTMLInputElement>) => {
    setFrdFile(event.target.files?.[0] ?? null);
  };

  const handleRemoveBrd = () => {
    setBrdFile(null);
    if (brdInputRef.current) {
      brdInputRef.current.value = "";
    }
  };

  const handleRemoveFrd = () => {
    clearFrdFile();
    if (frdInputRef.current) {
      frdInputRef.current.value = "";
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submit();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Specification Documents</CardTitle>
        <CardDescription>
          A Business Requirements Document is required. You may optionally add a Functional
          Requirements Document and free-text context to refine the generated test cases.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-6" noValidate>
          {/* BRD (mandatory) */}
          <div className="flex flex-col gap-2">
            <label htmlFor="brd-file-input" className="text-sm font-medium leading-none">
              Business Requirements Document (BRD)
              <span className="ml-0.5 text-destructive" aria-hidden="true">
                *
              </span>
            </label>
            <p className="text-xs text-muted-foreground">
              Mandatory &mdash; .pdf, .docx, or .txt
            </p>
            <div
              className={cn(
                "flex flex-wrap items-center gap-3 rounded-md border-2 border-dashed border-input p-4 transition-colors",
                showBrdInlineError && "border-destructive"
              )}
            >
              <label
                htmlFor="brd-file-input"
                className={cn(
                  buttonLabelClasses,
                  isSubmitting && "pointer-events-none opacity-50"
                )}
              >
                <UploadCloud className="h-4 w-4" aria-hidden="true" />
                Choose BRD file
              </label>
              <input
                ref={brdInputRef}
                id="brd-file-input"
                type="file"
                accept={ACCEPTED_FILE_TYPES}
                onChange={handleBrdChange}
                disabled={isSubmitting}
                aria-required="true"
                aria-invalid={showBrdInlineError}
                aria-describedby={showBrdInlineError ? "brd-file-error" : undefined}
                className="sr-only"
              />
              {brdFile ? (
                <SelectedFileChip file={brdFile} onRemove={handleRemoveBrd} disabled={isSubmitting} />
              ) : (
                <span className="text-sm text-muted-foreground">No file selected</span>
              )}
            </div>
            {showBrdInlineError ? (
              <p id="brd-file-error" role="alert" className="text-sm font-medium text-destructive">
                {errorMessage ?? BRD_MANDATORY_MESSAGE}
              </p>
            ) : null}
          </div>

          {/* FRD (optional) */}
          <div className="flex flex-col gap-2">
            <label htmlFor="frd-file-input" className="text-sm font-medium leading-none">
              Functional Requirements Document (FRD)
            </label>
            <p className="text-xs text-muted-foreground">Optional &mdash; .pdf, .docx, or .txt</p>
            <div className="flex flex-wrap items-center gap-3 rounded-md border-2 border-dashed border-input p-4">
              <label
                htmlFor="frd-file-input"
                className={cn(
                  buttonLabelClasses,
                  isSubmitting && "pointer-events-none opacity-50"
                )}
              >
                <UploadCloud className="h-4 w-4" aria-hidden="true" />
                Choose FRD file
              </label>
              <input
                ref={frdInputRef}
                id="frd-file-input"
                type="file"
                accept={ACCEPTED_FILE_TYPES}
                onChange={handleFrdChange}
                disabled={isSubmitting}
                className="sr-only"
              />
              {frdFile ? (
                <SelectedFileChip file={frdFile} onRemove={handleRemoveFrd} disabled={isSubmitting} />
              ) : (
                <span className="text-sm text-muted-foreground">No file selected</span>
              )}
            </div>
          </div>

          {/* Free-text context */}
          <div className="flex flex-col gap-2">
            <label htmlFor="context-textarea" className="text-sm font-medium leading-none">
              Additional Context
            </label>
            <Textarea
              id="context-textarea"
              value={context}
              onChange={(event) => setContext(event.target.value)}
              placeholder="Add guiding pointers, focus areas, or edge cases (optional)"
              disabled={isSubmitting}
              rows={4}
            />
          </div>

          <div>
            <Button type="submit" disabled={isBrdMissing || isSubmitting} aria-busy={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Generating&hellip;
                </>
              ) : (
                "Generate Test Cases"
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

const buttonLabelClasses =
  "inline-flex cursor-pointer items-center gap-2 whitespace-nowrap rounded-md border border-input bg-background px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";
