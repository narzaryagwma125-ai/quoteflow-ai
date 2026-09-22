import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuoteForm } from "@/components/QuoteForm";

function makeForm(onSave = async () => {}) {
  return render(
    <QuoteForm
      customers={[{ id: 1, name: "ACME" }]}
      taxRatePercent="7.5"
      defaultValues={{ issue_date: "2026-09-13", currency: "USD", discount: "0" }}
      onSave={onSave}
    />,
  );
}

describe("QuoteForm", () => {
  it("renders the empty state with one item row and totals", () => {
    makeForm();
    expect(screen.getByText("Details")).toBeInTheDocument();
    expect(screen.getByText("Services")).toBeInTheDocument();
    expect(screen.getByText("Pricing")).toBeInTheDocument();
    // subtotal + total are both $0.00 (two occurrences)
    expect(screen.getAllByText("$0.00").length).toBeGreaterThanOrEqual(2);
  });

  it("computes a live total including tax from dropdown selection", async () => {
    const user = userEvent.setup();
    makeForm();
    await user.type(screen.getByLabelText("Description"), "Deep clean");
    await user.type(screen.getByLabelText("Unit price"), "100");
    // 1 x 100 = $100.00 subtotal; 7.5% tax => $107.50 total
    expect(screen.getByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("$107.50")).toBeInTheDocument();
  });

  it("adds and removes item rows", async () => {
    const user = userEvent.setup();
    makeForm();
    await user.click(screen.getByRole("button", { name: "+ Add item" }));
    expect(screen.getAllByLabelText("Description").length).toBe(2);
    await user.click(screen.getByRole("button", { name: "Remove item 2" }));
    expect(screen.getAllByLabelText("Description").length).toBe(1);
  });

  it("validates required description before saving", async () => {
    const user = userEvent.setup();
    let saved = false;
    makeForm(async () => {
      saved = true;
    });
    await user.click(screen.getByRole("button", { name: "Save quote" }));
    expect(saved).toBe(false);
    expect(screen.getByText(/Every item needs a description/i)).toBeInTheDocument();
  });

  it("rejects invalid prices before saving", async () => {
    const user = userEvent.setup();
    let saved = false;
    makeForm(async () => {
      saved = true;
    });
    await user.type(screen.getByLabelText("Description"), "Deep clean");
    await user.type(screen.getByLabelText("Unit price"), "10.999");
    await user.click(screen.getByRole("button", { name: "Save quote" }));
    expect(saved).toBe(false);
    expect(screen.getByText(/Enter a valid price/i)).toBeInTheDocument();
  });

  it("shows an empty-customers note and an Add customer button", () => {
    render(
      <QuoteForm
        customers={[]}
        taxRatePercent="7.5"
        defaultValues={{ issue_date: "2026-09-13", currency: "USD", discount: "0" }}
        onSave={async () => {}}
      />,
    );
    expect(screen.getByText(/No customers yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add customer" })).toHaveAttribute("href", "/customers/new");
    expect(screen.getByRole("option", { name: "— No customer —" })).toBeInTheDocument();
  });

  it("renders — No customer — as the default dropdown option", () => {
    makeForm();
    const option = screen.getByRole("option", { name: "— No customer —" });
    expect(option).toBeInTheDocument();
    expect(option).toHaveValue("");
  });

  it("renders a Unit dropdown with the expected options", () => {
    makeForm();
    const unitSelect = screen.getByLabelText("Unit") as HTMLSelectElement;
    expect(unitSelect.tagName).toBe("SELECT");
    const options = Array.from(unitSelect.options).map((o) => o.textContent);
    expect(options).toContain("Hour");
    expect(options).toContain("Service");
    expect(options).toContain("Item");
    expect(options).toContain("— Unit —");
  });

  it("renders all five supported currencies and defaults to INR", () => {
    render(
      <QuoteForm
        customers={[]}
        taxRatePercent="0"
        defaultValues={{ issue_date: "2026-09-13" }}
        onSave={async () => {}}
      />,
    );
    const currencySelect = screen.getByLabelText("Currency") as HTMLSelectElement;
    const options = Array.from(currencySelect.options).map((o) => o.value);
    expect(options).toEqual(["INR", "USD", "CAD", "GBP", "AUD"]);
    expect(currencySelect.value).toBe("INR");
  });

  it("re-renders totals in the selected currency", async () => {
    const user = userEvent.setup();
    makeForm();
    await user.type(screen.getByLabelText("Description"), "Deep clean");
    await user.type(screen.getByLabelText("Unit price"), "100");
    await user.selectOptions(screen.getByLabelText("Currency"), "GBP");
    expect(screen.getByText("£100.00")).toBeInTheDocument();
  });
});