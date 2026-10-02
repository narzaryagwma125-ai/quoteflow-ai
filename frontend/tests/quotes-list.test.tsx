import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ActionsMenu } from "@/components/ActionsMenu";
import { QuoteList } from "@/components/QuoteList";
import type { Quote } from "@/types";

function quote(over: Partial<Quote> = {}): Quote {
  return {
    id: 1,
    quote_number: "Q-1001",
    customer_id: null,
    status: "draft",
    issue_date: "2026-09-10",
    expiry_date: null,
    currency: "USD",
    subtotal_minor: 10000,
    discount_minor: 0,
    tax_minor: 0,
    total_minor: 10000,
    notes: "",
    terms: "",
    created_at: "2026-09-10T10:00:00Z",
    updated_at: "2026-09-10T10:00:00Z",
    items: [],
    breakdown: null,
    customer_name: "Acme Corp",
    public_link_token: "",
    has_public_link: false,
    ...over,
  };
}

const noop = () => {};

const handlers = {
  onDocx: vi.fn(),
  onPdf: vi.fn(),
  onDuplicate: vi.fn(),
  onDelete: vi.fn(),
};

describe("ActionsMenu", () => {
  it("starts closed: DOCX, PDF, Duplicate and Delete are hidden", () => {
    render(<ActionsMenu onDocx={noop} onPdf={noop} onDuplicate={noop} onDelete={noop} />);
    expect(screen.queryByText("DOCX")).not.toBeInTheDocument();
    expect(screen.queryByText("PDF")).not.toBeInTheDocument();
    expect(screen.queryByText("Duplicate")).not.toBeInTheDocument();
    expect(screen.queryByText("Delete")).not.toBeInTheDocument();
  });

  it("opens to expose DOCX, PDF, Duplicate and Delete", async () => {
    render(<ActionsMenu onDocx={noop} onPdf={noop} onDuplicate={noop} onDelete={noop} />);
    await userEvent.click(screen.getByRole("button", { name: "Actions" }));
    expect(screen.getByText("DOCX")).toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByText("Duplicate")).toBeInTheDocument();
    expect(screen.getByText("Delete")).toBeInTheDocument();
  });

  it("fires the callback for a menu item and closes afterwards", async () => {
    const onDuplicate = vi.fn();
    render(<ActionsMenu onDocx={noop} onPdf={noop} onDuplicate={onDuplicate} onDelete={noop} />);
    await userEvent.click(screen.getByRole("button", { name: "Actions" }));
    await userEvent.click(screen.getByText("Duplicate"));
    expect(onDuplicate).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Duplicate")).not.toBeInTheDocument();
  });

  it("disables the trigger while a row action is busy", () => {
    render(<ActionsMenu busy onDocx={noop} onPdf={noop} onDuplicate={noop} onDelete={noop} />);
    expect(screen.getByRole("button", { name: "Actions" })).toBeDisabled();
  });
});

describe("QuoteList", () => {
  it("renders both the desktop table and the responsive mobile cards", () => {
    render(<QuoteList rows={[quote()]} busyId={null} handlers={handlers} />);
    expect(screen.getByTestId("desktop-quotes-table")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-quote-cards")).toBeInTheDocument();
  });

  it("shows the amount and currency with a separating space", () => {
    render(<QuoteList rows={[quote({ total_minor: 50400, currency: "USD" })]} busyId={null} handlers={handlers} />);
    expect(screen.getAllByText("$504.00 USD")).toHaveLength(2);
    expect(screen.queryAllByText("$504.00USD")).toHaveLength(0);
  });

  it("keeps View and Edit visible and out of the menu", () => {
    render(<QuoteList rows={[quote(), quote({ id: 2, quote_number: "Q-1002" })]} busyId={null} handlers={handlers} />);
    const table = screen.getByTestId("desktop-quotes-table");
    expect(within(table).getAllByRole("link", { name: "View" })).toHaveLength(2);
    expect(within(table).getAllByRole("link", { name: "Edit" })).toHaveLength(2);
  });

  it("hides DOCX/PDF/Duplicate/Delete until the menu opens", async () => {
    render(<QuoteList rows={[quote()]} busyId={null} handlers={handlers} />);
    expect(screen.queryByText("DOCX")).not.toBeInTheDocument();
    expect(screen.queryByText("PDF")).not.toBeInTheDocument();
    expect(screen.queryByText("Delete")).not.toBeInTheDocument();

    const table = screen.getByTestId("desktop-quotes-table");
    await userEvent.click(within(table).getByRole("button", { name: "Actions" }));
    expect(screen.getByText("DOCX")).toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByText("Delete")).toBeInTheDocument();
  });

  it("passes the right quote and handler through the actions menu", async () => {
    const q = quote({ id: 42, quote_number: "Q-42", status: "sent" });
    const onDocx = vi.fn();
    const onPdf = vi.fn();
    const onDuplicate = vi.fn();
    const onDelete = vi.fn();
    render(
      <QuoteList
        rows={[q]}
        busyId={null}
        handlers={{ onDocx, onPdf, onDuplicate, onDelete }}
      />,
    );

    const table = screen.getByTestId("desktop-quotes-table");
    const dup = within(table).getByRole("button", { name: "Actions" });
    await userEvent.click(dup);
    await userEvent.click(screen.getByText("Duplicate"));
    expect(onDuplicate).toHaveBeenCalledWith(q);

    await userEvent.click(within(table).getByRole("button", { name: "Actions" }));
    await userEvent.click(screen.getByText("Delete"));
    expect(onDelete).toHaveBeenCalledWith(q);
    expect(onDocx).not.toHaveBeenCalled();
    expect(onPdf).not.toHaveBeenCalled();
  });

  it("disables the row's actions while that row is busy", () => {
    render(<QuoteList rows={[quote({ id: 1 }), quote({ id: 2 })]} busyId={1} handlers={handlers} />);
    const table = screen.getByTestId("desktop-quotes-table");
    const triggers = within(table).getAllByRole("button", { name: "Actions" });
    expect(triggers).toHaveLength(2);
    expect(triggers[0]).toBeDisabled();
    expect(triggers[1]).not.toBeDisabled();
  });
});

describe("QuoteList empty state", () => {
  it("renders without rows or errors", () => {
    render(<QuoteList rows={[]} busyId={null} handlers={handlers} />);
    expect(screen.getByTestId("desktop-quotes-table")).toBeInTheDocument();
  });
});