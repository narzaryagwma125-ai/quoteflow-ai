import type { QuoteFormPayload } from "@/components/QuoteForm";
import type { QuoteItemInput } from "@/types";

// Money convention: the quote API accepts MAJOR units (dollars) and plain
// quantity values. The backend converts dollars -> cents exactly once via
// QuoteItemIn.unit_price_minor / decimal_to_minor.
// NEVER call toMinor() on quantity, unit_price, or discount here — doing so
// double-converts (3 -> 300 quantity, 150 -> $15,000 price).
export interface QuoteItemApiBody {
  description: string;
  quantity: string;
  unit: string;
  unit_price: string;
  sort_order: number;
}

export function quoteItemsBody(items: QuoteItemInput[]): QuoteItemApiBody[] {
  return items.map((it) => ({
    description: it.description,
    quantity: it.quantity,
    unit: it.unit,
    unit_price: it.unit_price,
    sort_order: it.sort_order,
  }));
}

function discountBody(discount: string): string {
  return discount.trim() === "" ? "0" : discount;
}

export function buildQuoteCreateBody(payload: QuoteFormPayload) {
  const today = new Date().toISOString().slice(0, 10);
  return {
    customer_id: payload.customer_id,
    quote_number: null,
    currency: payload.currency,
    issue_date: payload.issue_date || today,
    expiry_date: payload.expiry_date,
    discount: discountBody(payload.discount),
    notes: payload.notes,
    terms: payload.terms,
    items: quoteItemsBody(payload.items),
  };
}

export function buildQuoteUpdateBody(payload: QuoteFormPayload) {
  return {
    customer_id: payload.customer_id,
    currency: payload.currency,
    issue_date: payload.issue_date,
    expiry_date: payload.expiry_date,
    discount: discountBody(payload.discount),
    notes: payload.notes,
    terms: payload.terms,
    items: quoteItemsBody(payload.items),
  };
}