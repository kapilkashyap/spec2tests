import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { FileUploadPanel } from "@/components/FileUploadPanel";
import { useTestCaseGeneration } from "@/hooks/useTestCaseGeneration";

/**
 * Thin wrapper that exercises the real `useTestCaseGeneration` hook (rather
 * than a mock) so these component tests validate the actual file-selection
 * and BRD-mandatory validation wiring, not a stand-in.
 */
function Harness() {
  const generation = useTestCaseGeneration();
  return <FileUploadPanel generation={generation} />;
}

function makeFile(name: string, type = "application/pdf"): File {
  return new File(["dummy file contents"], name, { type });
}

describe("FileUploadPanel", () => {
  it("disables the Generate button when no BRD file has been selected", () => {
    render(<Harness />);

    const submitButton = screen.getByRole("button", { name: /generate test cases/i });
    expect(submitButton).toBeDisabled();
  });

  it("enables the Generate button once a supported .pdf BRD file is selected", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const brdInput = screen.getByLabelText(/business requirements document/i, {
      selector: "input",
    });
    const submitButton = screen.getByRole("button", { name: /generate test cases/i });

    expect(submitButton).toBeDisabled();

    await user.upload(brdInput, makeFile("requirements.pdf"));

    expect(submitButton).toBeEnabled();
    expect(screen.getByText("requirements.pdf")).toBeInTheDocument();
  });

  it("shows a validation error and keeps submission disabled for an unsupported extension", async () => {
    // `applyAccept: false` is required here because the real BRD `<input>`
    // declares `accept=".pdf,.docx,.txt"`; by default user-event silently
    // filters out files that don't match `accept` before firing a change
    // event, which would prevent this negative case from ever reaching the
    // component's own extension validation logic.
    const user = userEvent.setup({ applyAccept: false });
    render(<Harness />);

    const brdInput = screen.getByLabelText(/business requirements document/i, {
      selector: "input",
    });
    const submitButton = screen.getByRole("button", { name: /generate test cases/i });

    await user.upload(brdInput, makeFile("malware.exe", "application/octet-stream"));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/unsupported brd file type/i);
    expect(submitButton).toBeDisabled();
    // The invalid file must not have been accepted as the selected BRD file.
    expect(screen.queryByText("malware.exe")).not.toBeInTheDocument();
  });
});
