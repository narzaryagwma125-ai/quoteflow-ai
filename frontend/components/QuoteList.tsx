"use client";

import Link from "next/link";
import { ActionsMenu } from "@/components/ActionsMenu";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate, formatMoneyWithCode } from "@/lib/format";
import type { Quote } from "@/types";

export interface QuoteListHandlers {
  onDocx: (q: Quote) => void;
  onPdf: (q: Quote) => void;
  onDuplicate: (q: Quote) => void;
  onDelete: (q: Quote) => void;
}

/**
 * Recent-quotes list for the dashboard. Reads the same rows on every screen
 * size: a compact card layout on small screens and the full table on lg+.
 * View and Edit stay visible one click away; DOCX, PDF, Duplicate and Delete
 * live behind the per-row actions menu.
 */
export function QuoteList({
  rows,
  busyId,
  handlers,
}: {
  rows: Quote[];
  busyId: number | null;
  handlers: QuoteListHandlers;
}) {
  const actions = (q: Quote) => ({
    busy: busyId === q.id,
    onDocx: () => handlers.onDocx(q),
    onPdf: () => handlers.onPdf(q),
    onDuplicate: () => handlers.onDuplicate(q),
    onDelete: () => handlers.onDelete(q),
  });

  return (
    <>
      {/* Mobile cards */}
      <div data-testid="mobile-quote-cards" className="space-y-3 lg:hidden">
        {rows.map((q) => {
          const a = actions(q);
          return (
            <div key={q.id} className="rounded-lg border border-slate-200 p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <Link
                    href={`/quotes/${q.id}`}
                    className="block font-medium text-slate-800 hover:text-brand-600"
                  >
                    {q.quote_number}
                  </Link>
                  <p className="truncate text-sm text-slate-600">{q.customer_name || "—"}</p>
                </div>
                <StatusBadge status={q.status} />
              </div>
              <div className="mt-3 flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs text-slate-500">{formatDate(q.issue_date)}</p>
                  <p className="text-sm font-semibold text-slate-900">
                    {formatMoneyWithCode(q.total_minor, q.currency)}
                  </p>
                </div>
                <ActionsMenu {...a} />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link href={`/quotes/${q.id}`}>
                  <Button variant="ghost" size="sm">View</Button>
                </Link>
                <Link href={`/quotes/${q.id}?edit=1`}>
                  <Button variant="ghost" size="sm">Edit</Button>
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      {/* Desktop table */}
      <div className="hidden overflow-x-auto lg:block" data-testid="desktop-quotes-table">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <th className="px-2 py-2 font-semibold">Number</th>
              <th className="hidden px-2 py-2 font-semibold sm:table-cell">Customer</th>
              <th className="px-2 py-2 font-semibold">Date</th>
              <th className="px-2 py-2 font-semibold">Status</th>
              <th className="px-2 py-2 text-right font-semibold">Amount</th>
              <th className="px-2 py-2 text-right font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((q) => {
              const a = actions(q);
              return (
                <tr key={q.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-2 py-2">
                    <Link href={`/quotes/${q.id}`} className="font-medium text-slate-800 hover:text-brand-600">
                      {q.quote_number}
                    </Link>
                  </td>
                  <td className="hidden px-2 py-2 text-slate-600 sm:table-cell">{q.customer_name || "—"}</td>
                  <td className="px-2 py-2 text-slate-600">{formatDate(q.issue_date)}</td>
                  <td className="px-2 py-2">
                    <StatusBadge status={q.status} />
                  </td>
                  <td className="px-2 py-2 text-right">
                    <span className="whitespace-nowrap font-semibold text-slate-900">
                      {formatMoneyWithCode(q.total_minor, q.currency)}
                    </span>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex justify-end gap-1">
                      <Link href={`/quotes/${q.id}`}>
                        <Button variant="ghost" size="sm">View</Button>
                      </Link>
                      <Link href={`/quotes/${q.id}?edit=1`}>
                        <Button variant="ghost" size="sm">Edit</Button>
                      </Link>
                      <ActionsMenu {...a} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}