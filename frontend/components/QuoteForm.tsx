"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { CurrencyAmount } from "@/components/CurrencyAmount";
import { Select } from "@/components/Select";
import { Textarea } from "@/components/Textarea";
import { Card } from "@/components/Card";
import { AIAssist } from "@/components/AIAssist";
import { CURRENCY_SYMBOLS, minorToDollars, toMinor } from "@/lib/format";
import type { CurrencyCode, Quote, QuoteBreakdown, QuoteItemInput } from "@/types";

function dollarsToCents(value: string): number {
  const minor = toMinor(value);
  return minor ?? 0;
}

export interface QuoteFormPayload {
  customer_id: number | null;
  issue_date: string;
  expiry_date: string | null;
  currency: CurrencyCode;
  discount: string;
  notes: string;
  terms: string;
  items: QuoteItemInput[];
}

// Tolerance to keep snapshots deterministic for minor-unit arithmetic.
const round = (n: number) => Math.round(n);

function computeBreakdown(
  items: QuoteItemInput[],
  discountDollars: string,
  currency: string,
): QuoteBreakdown {
  const subtotal = round(
    items.reduce(
      (sum, it) =>
        sum + Math.max(0, Number(it.quantity)) * dollarsToCents(it.unit_price),
      0,
    ),
  );
  const discount = Math.min(subtotal, Math.max(0, dollarsToCents(discountDollars)));
  return {
    subtotal_minor: subtotal,
    discount_minor: discount,
    tax_minor: 0,
    total_minor: subtotal - discount,
    tax_rate_percent: "0",
  };
}

const UNIT_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "— Unit —" },
  { value: "service", label: "Service" },
  { value: "item", label: "Item" },
  { value: "hour", label: "Hour" },
  { value: "day", label: "Day" },
  { value: "page", label: "Page" },
  { value: "kg", label: "Kilogram" },
];

const emptyItem = (sort_order: number): QuoteItemInput => ({
  description: "",
  quantity: "1",
  unit: "",
  unit_price: "",
  sort_order,
});

const itemFieldId = (index: number, field: string) => `quote-item-${index}-${field}`;

export function QuoteForm({
  initial,
  customers,
  defaultValues,
  taxRatePercent = "0",
  businessName = "",
  quoteNumber = "",
  onCancel,
  onSave,
}: {
  initial?: Quote | null;
  customers: { id: number; name: string }[];
  defaultValues?: Partial<QuoteFormPayload>;
  taxRatePercent?: string;
  businessName?: string;
  quoteNumber?: string;
  onCancel?: () => void;
  onSave: (payload: QuoteFormPayload) => Promise<void>;
}) {
  const [currency, setCurrency] = useState<CurrencyCode>(
    (initial?.currency ?? defaultValues?.currency ?? "INR") as CurrencyCode,
  );
  const [customerId, setCustomerId] = useState<string>(
    String(initial?.customer_id ?? defaultValues?.customer_id ?? ""),
  );
  const [issueDate, setIssueDate] = useState(initial?.issue_date ?? defaultValues?.issue_date ?? "");
  const [expiryDate, setExpiryDate] = useState(
    initial?.expiry_date ?? defaultValues?.expiry_date ?? "",
  );
  const [discount, setDiscount] = useState(
    initial ? minorToDollars(initial.discount_minor) : defaultValues?.discount ?? "0",
  );
  const [notes, setNotes] = useState(initial?.notes ?? defaultValues?.notes ?? "");
  const [terms, setTerms] = useState(initial?.terms ?? defaultValues?.terms ?? "");
  const [items, setItems] = useState<QuoteItemInput[]>(
    initial && initial.items.length
      ? initial.items.map((it) => ({
          description: it.description,
          quantity: it.quantity,
          unit: it.unit,
          unit_price: minorToDollars(it.unit_price_minor),
          sort_order: it.sort_order,
        }))
      : defaultValues?.items?.length
        ? defaultValues.items
        : [emptyItem(0)],
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiTarget, setAiTarget] = useState(0);

  const selectedCustomer = customers.find((c) => c.id === Number(customerId))?.name ?? "";

  const updateItem = (index: number, patch: Partial<QuoteItemInput>) => {
    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, ...patch } : it)));
  };

  const breakdown = computeBreakdown(items, discount, currency);
  const rate = Math.max(0, parseFloat(taxRatePercent || "0"));
  if (rate > 0) {
    const taxable = Math.max(0, breakdown.subtotal_minor - breakdown.discount_minor);
    const tax = round(taxable * (rate / 100));
    breakdown.tax_minor = tax;
    breakdown.total_minor = breakdown.total_minor + tax;
    breakdown.tax_rate_percent = String(rate);
  }

  const validate = (): string | null => {
    if (!issueDate) return "Pick an issue date.";
    if (items.length === 0) return "Add at least one service item.";
    for (const it of items) {
      if (!it.description.trim()) return "Every item needs a description.";
      const q = toMinor(it.quantity);
      if (q === null || q <= 0) return `Quantity must be a positive number for “${it.description || "item"}”.`;
      const price = toMinor(it.unit_price);
      if (price === null) return `Enter a valid price for “${it.description}”.`;
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await onSave({
        customer_id: customerId ? Number(customerId) : null,
        issue_date: issueDate,
        expiry_date: expiryDate || null,
        currency,
        discount: discount.trim() === "" ? "0" : discount,
        notes,
        terms,
        items: items
          .filter((it) => it.description.trim() !== "")
          .map((it, idx) => ({ ...it, sort_order: idx })),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save quote.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      <Card title="Details">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <Select label="Customer" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">— No customer —</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <div className="mt-1.5 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {customers.length === 0
                ? "No customers yet. Add one to attach this quote."
                : `${customers.length} customer${customers.length === 1 ? "" : "s"} available.`}
            </span>
            <Button type="button" variant="secondary" size="sm">
              <Link href="/customers/new">Add customer</Link>
            </Button>
          </div>
        </div>
          <Select
            label="Currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value as CurrencyCode)}
          >
            <option value="INR">INR (₹)</option>
            <option value="USD">USD ($)</option>
            <option value="CAD">CAD (CA$)</option>
            <option value="GBP">GBP (£)</option>
            <option value="AUD">AUD (A$)</option>
          </Select>
          <Input
            type="date"
            label="Issue date"
            value={issueDate}
            onChange={(e) => setIssueDate(e.target.value)}
          />
          <Input
            type="date"
            label="Expiry date (optional)"
            value={expiryDate}
            onChange={(e) => setExpiryDate(e.target.value)}
          />
        </div>
      </Card>

      <Card title="Services">
        <div className="space-y-4">
          {items.map((item, idx) => (
            <div key={idx} className="grid grid-cols-12 items-end gap-3 rounded-lg border border-slate-200 p-3">
              <div className="col-span-12 sm:col-span-4">
                <Input
                  id={itemFieldId(idx, "description")}
                  label="Description"
                  value={item.description}
                  onChange={(e) => updateItem(idx, { description: e.target.value })}
                />
              </div>
              <div className="col-span-12 sm:col-span-2">
                <Select
                  label="Unit"
                  id={itemFieldId(idx, "unit")}
                  value={item.unit}
                  onChange={(e) => updateItem(idx, { unit: e.target.value })}
                >
                  {UNIT_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </Select>
              </div>
              <div className="col-span-4 sm:col-span-2">
                <Input
                  id={itemFieldId(idx, "qty")}
                  label="Qty"
                  inputMode="decimal"
                  value={item.quantity}
                  onChange={(e) => updateItem(idx, { quantity: e.target.value })}
                />
              </div>
              <div className="col-span-8 sm:col-span-2">
                <Input
                  id={itemFieldId(idx, "price")}
                  label="Unit price"
                  inputMode="decimal"
                  prefix={CURRENCY_SYMBOLS[currency]}
                  value={item.unit_price}
                  onChange={(e) => updateItem(idx, { unit_price: e.target.value })}
                />
              </div>
              <div className="col-span-12 sm:col-span-2 flex items-center gap-1 pb-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`AI assist item ${idx + 1}`}
                  onClick={() => {
                    setAiTarget(idx);
                    setAiOpen(true);
                  }}
                >
                  AI assist
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove item ${idx + 1}`}
                  onClick={() => setItems((prev) => prev.filter((_, i) => i !== idx))}
                >
                  Remove
                </Button>
              </div>
            </div>
          ))}
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setItems((prev) => [...prev, emptyItem(prev.length)])}
          >
            + Add item
          </Button>
        </div>
      </Card>

      <Card title="Pricing">
        <div className="max-w-xs space-y-4">
          <Input label="Discount (optional)" prefix={CURRENCY_SYMBOLS[currency] ?? "$"} value={discount} onChange={(e) => setDiscount(e.target.value)} hint="Lumped discount applied before tax." />
          <dl className="space-y-1 rounded-lg bg-slate-50 p-4 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Subtotal</dt>
              <dd className="font-medium"><CurrencyAmount minor={breakdown.subtotal_minor} currency={currency} /></dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Discount</dt>
              <dd className="font-medium">−<CurrencyAmount minor={breakdown.discount_minor} currency={currency} /></dd>
            </div>
            {breakdown.tax_minor > 0 && (
              <div className="flex justify-between">
                <dt className="text-slate-500">Tax ({breakdown.tax_rate_percent}%)</dt>
                <dd className="font-medium"><CurrencyAmount minor={breakdown.tax_minor} currency={currency} /></dd>
              </div>
            )}
            <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold">
              <dt>Total</dt>
              <dd><CurrencyAmount minor={breakdown.total_minor} currency={currency} /></dd>
            </div>
          </dl>
        </div>
      </Card>

      <Card title="Terms & notes">
        <div className="grid grid-cols-1 gap-4">
          <Textarea label="Terms" value={terms} onChange={(e) => setTerms(e.target.value)} placeholder="Payment due within 14 days…" />
          <Textarea label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Visible to the customer." />
        </div>
      </Card>

      <div className="flex justify-end gap-3">
        <Button variant="secondary" type="button" onClick={onCancel ?? (() => window.history.back())}>
          Cancel
        </Button>
        <Button type="submit" loading={saving}>
          Save quote
        </Button>
      </div>

      <AIAssist
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        serviceName={items[aiTarget]?.description ?? ""}
        currentDescription={items[aiTarget]?.description ?? ""}
        businessName={businessName}
        customerName={selectedCustomer}
        quoteNumber={quoteNumber || ""}
        onInsertDescription={(text) =>
          setItems((prev) => prev.map((it, i) => (i === aiTarget ? { ...it, description: text } : it)))
        }
        onInsertNotes={(text) => setNotes((prev) => (prev ? `${prev}\n\n${text}` : text))}
      />
    </form>
  );
}