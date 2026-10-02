"use client";

import { Button } from "@/components/Button";

export function PricingCard({
  name,
  price,
  cadence = "/month",
  tagline,
  features,
  cta,
  highlight = false,
  onSelect,
}: {
  name: string;
  price: string;
  cadence?: string;
  tagline: string;
  features: string[];
  cta: string;
  highlight?: boolean;
  onSelect?: () => void;
}) {
  return (
    <div
      className={`flex flex-col rounded-2xl border p-6 ${
        highlight ? "border-brand-500 bg-indigo-50/60 shadow-xl shadow-indigo-100" : "border-slate-200 bg-white shadow-sm"
      }`}
    >
      <h3 className="text-lg font-semibold text-slate-800">{name}</h3>
      <p className="mt-1 text-sm text-slate-500">{tagline}</p>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="text-3xl font-bold">{price}</span>
        <span className="text-sm text-slate-500">{cadence}</span>
      </div>
      <ul className="mt-5 flex-1 space-y-2 text-sm text-slate-700">
        {features.map((f) => (
          <li key={f} className="flex gap-2">
            <span aria-hidden className="text-brand-600">
              ✓
            </span>
            {f}
          </li>
        ))}
      </ul>
      <div className="mt-6">
        <Button variant={highlight ? "primary" : "secondary"} className="w-full" onClick={onSelect}>
          {cta}
        </Button>
      </div>
    </div>
  );
}