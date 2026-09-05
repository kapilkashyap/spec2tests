import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { TestCase, TestCasePriority } from "@/lib/types";

export interface TestCaseTableProps {
  /** Test cases returned from `POST /api/generate-test-cases`, in generation order. */
  testCases: TestCase[];
}

/** Maps a test case's priority to the `Badge` color variant used to render it. */
const PRIORITY_BADGE_VARIANT: Record<TestCasePriority, "high" | "medium" | "low"> = {
  High: "high",
  Medium: "medium",
  Low: "low",
};

/**
 * Renders a `<ul>` bullet list for a string array cell (e.g. Pre-conditions),
 * falling back to an em-dash placeholder when the array is empty — the
 * backend model defaults `preconditions` to `[]`.
 */
function BulletListCell({ items }: { items: string[] }) {
  if (!items || items.length === 0) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <ul className="list-disc space-y-1 pl-4">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

/**
 * Renders an `<ol>` ordered list for a string array cell (e.g. Test Steps),
 * preserving generation order, falling back to an em-dash placeholder when
 * the array is empty.
 */
function OrderedListCell({ items }: { items: string[] }) {
  if (!items || items.length === 0) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <ol className="list-decimal space-y-1 pl-4">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ol>
  );
}

/**
 * Renders the "Priority" column value as a color-coded `Badge`:
 * High -> destructive/red, Medium -> warning/amber, Low -> neutral/green.
 */
function PriorityBadge({ priority }: { priority: TestCasePriority }) {
  const variant = PRIORITY_BADGE_VARIANT[priority] ?? "medium";
  return <Badge variant={variant}>{priority}</Badge>;
}

/**
 * Displays generated test cases in the seven POC-mandated columns:
 * Test Case ID, Requirement Reference, Test Scenario (title + description),
 * Pre-conditions, Test Steps, Expected Result, and Priority.
 *
 * Renders an empty-state `Card` when there are no test cases yet, and wraps
 * the table in a scrollable container so long result sets remain usable.
 */
function TestCaseTable({ testCases }: TestCaseTableProps) {
  if (testCases.length === 0) {
    return (
      <Card className="flex min-h-[200px] items-center justify-center">
        <CardContent className="flex items-center justify-center p-10 text-center">
          <p className="text-sm text-muted-foreground">
            No test cases yet — upload a BRD and click Generate to get started.
          </p>
        </CardContent>
      </Card>
    );
  }

  const count = testCases.length;

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        Showing {count} test case{count === 1 ? "" : "s"}
      </p>
      <div className="max-h-[70vh] overflow-y-auto overflow-x-auto rounded-md border border-border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-card">
            <TableRow>
              <TableHead>Test Case ID</TableHead>
              <TableHead>Requirement Reference</TableHead>
              <TableHead>Test Scenario</TableHead>
              <TableHead>Pre-conditions</TableHead>
              <TableHead>Test Steps</TableHead>
              <TableHead>Expected Result</TableHead>
              <TableHead>Priority</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {testCases.map((testCase) => (
              <TableRow key={testCase.id}>
                <TableCell className="align-top font-medium">{testCase.id}</TableCell>
                <TableCell className="align-top">
                  {testCase.requirement_reference ? (
                    testCase.requirement_reference
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="align-top">
                  <div className="min-w-[16rem] space-y-1">
                    <p className="font-medium">{testCase.title}</p>
                    {testCase.description ? (
                      <p className="text-xs text-muted-foreground">{testCase.description}</p>
                    ) : null}
                  </div>
                </TableCell>
                <TableCell className="min-w-[12rem] align-top">
                  <BulletListCell items={testCase.preconditions} />
                </TableCell>
                <TableCell className="min-w-[16rem] align-top">
                  <OrderedListCell items={testCase.steps} />
                </TableCell>
                <TableCell className="min-w-[14rem] align-top">
                  {testCase.expected_result ? (
                    testCase.expected_result
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="align-top">
                  <PriorityBadge priority={testCase.priority} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export default TestCaseTable;
export { TestCaseTable };
