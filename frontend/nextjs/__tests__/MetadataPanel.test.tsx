import { render, screen, within } from "@testing-library/react";
import MetadataPanel from "@/components/MetadataPanel";
import { mockReport, mockReportNullSeverity } from "@/lib/mock-data";

describe("MetadataPanel", () => {
  it("renders highest severity when present", () => {
    render(<MetadataPanel metadata={mockReport.metadata} />);
    const card = screen.getByText("Highest Severity").closest("div")!;
    expect(within(card).getByText("HIGH")).toBeInTheDocument();
  });

  it("renders 'None' when highest_severity_finding is null", () => {
    render(<MetadataPanel metadata={mockReportNullSeverity.metadata} />);
    expect(screen.getByText("None")).toBeInTheDocument();
  });

  it("renders all five severity counts", () => {
    render(<MetadataPanel metadata={mockReport.metadata} />);
    expect(screen.getByText(/CRITICAL: 0/)).toBeInTheDocument();
    expect(screen.getByText(/HIGH: 1/)).toBeInTheDocument();
    expect(screen.getByText(/MEDIUM: 2/)).toBeInTheDocument();
    expect(screen.getByText(/LOW: 0/)).toBeInTheDocument();
    expect(screen.getByText(/INFORMATIONAL: 0/)).toBeInTheDocument();
  });

  it("renders metadata fields", () => {
    render(<MetadataPanel metadata={mockReport.metadata} />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Layered Architecture")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
