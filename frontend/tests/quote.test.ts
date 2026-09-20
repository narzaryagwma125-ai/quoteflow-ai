import { describe, expect, it } from "vitest";
import { buildQuoteCreateBody, buildQuoteUpdateBody, quoteItemsBody } from "@/lib/quote";
import type { QuoteFormPayload } from "@/components/QuoteForm";

function payload(overrides: Partial<QuoteFormPayload> = {}): QuoteFormPayload {
  return {
    customer_id: 7,
    currency: "USD",
    issue_date: "2026-09-14",
    expiry_date: "2026-10-14",
    discount: "0",
    notes: "",
    terms: "",
    items: [
      { description: "Deep clean", quantity: "3", unit: "hour", unit_price: "150", sort_order: 0 },
    ],
    ...overrides,
  };
}

describe("quote API payload money convention", () => {
  it("keeps quantity 3 as 3 (never multiplied by 100)", () => {
    const body = buildQuoteCreateBody(payload());
    expect(body.items[0].quantity).toBe("3");
    expect(Number(body.items[0].quantity)).toBe(3);
  });

  it("keeps unit price 150 as major dollars (never sent as cents)", () => {
    const body = buildQuoteCreateBody(payload());
    expect(body.items[0].unit_price).toBe("150");
    expect(Number(body.items[0].unit_price)).toBe(150);
  });

  it("round-trips line math exactly: 3 x 150 = 450, 12% => 54, total 504", () => {
    const body = buildQuoteCreateBody(payload({ discount: "0" }));
    const q = Number(body.items[0].quantity);
    const p = Number(body.items[0].unit_price);
    const line = q * p;
    const tax = Math.round(line * 0.12);
    expect(line).toBe(450);
    expect(tax).toBe(54);
    expect(line + tax).toBe(504);
  });

  it("sends discount in major dollars", () => {
    const body = buildQuoteCreateBody(payload({ discount: "20" }));
    expect(body.discount).toBe("20");
    expect(Number(body.discount)).toBe(20);
    // empty discount normalizes to "0", never to 0 * 100 ambiguity
    expect(buildQuoteCreateBody(payload({ discount: "  " })).discount).toBe("0");
  });

  it("update body has no quote_number and matches create convention", () => {
    const create = buildQuoteCreateBody(payload());
    const update = buildQuoteUpdateBody(payload());
    expect(update).not.toHaveProperty("quote_number");
    expect(create.items[0].quantity).toBe(update.items[0].quantity);
    expect(create.items[0].unit_price).toBe(update.items[0].unit_price);
  });

  it("quoteItemsBody maps every field without conversion", () => {
    const items = quoteItemsBody(payload().items);
    expect(items).toEqual([
      { description: "Deep clean", quantity: "3", unit: "hour", unit_price: "150", sort_order: 0 },
    ]);
  });
});