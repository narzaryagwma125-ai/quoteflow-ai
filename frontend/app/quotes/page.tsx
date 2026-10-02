"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Loading } from "@/components/Loading";
import { CurrencyAmount } from "@/components/CurrencyAmount";
import { api, asList, asNumber, isRecord } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Quote, QuoteStatus } from "@/types";

const TABS: { key: QuoteStatus | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "draft", label: "Draft" },
  { key: "sent", label: "Sent" },
  { key: "viewed", label: "Viewed" },
  { key: "accepted", label: "Accepted" },
  { key: "rejected", label: "Rejected" },
  { key: "expired", label: "Expired" },
];

export default function QuotesPage() {
  const [rows, setRows] = useState<Quote[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState<QuoteStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 20;

  const load = useCallback(async (p: number, status: QuoteStatus | "all") => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ page: String(p), page_size: String(pageSize) });
      if (status !== "all") qs.set("status", status);
      const res = await api<unknown>(`/quotes?${qs.toString()}`);
      setRows(asList<Quote>(res, []));
      setTotal(isRecord(res) ? asNumber(res.total, 0) : 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quotes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(page, tab);
  }, [load, page, tab]);

  const selectTab = (key: QuoteStatus | "all") => {
    setTab(key);
    setPage(1);
  };

  return (
    <RequireAuth>
      <DashboardShell>
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-slate-900">Quotes</h1>
          <Link href="/quotes/new">
            <Button>New quote</Button>
          </Link>
        </div>
        <Card>
          <div className="mb-4 flex flex-wrap gap-2">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => selectTab(t.key)}
                className={`rounded-full px-3 py-1 text-sm font-medium ${
                  tab === t.key ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {error && <div className="mb-4 text-sm text-red-600">{error}</div>}
          {loading ? (
            <Loading />
          ) : (
            <>
              <DataTable
                rows={rows}
                onRowClick={(q) => (window.location.href = `/quotes/${q.id}`)}
                emptyMessage="No quotes match this view."
                columns={[
                  { key: "number", header: "Number", render: (q) => <span className="font-medium">{q.quote_number}</span> },
                  { key: "customer", header: "Customer", render: (q) => q.customer_name || "—" },
                  { key: "status", header: "Status", render: (q) => <StatusBadge status={q.status} /> },
                  { key: "issued", header: "Issued", render: (q) => formatDate(q.issue_date) },
                  { key: "total", header: "Total", render: (q) => <CurrencyAmount minor={q.total_minor} currency={q.currency} /> },
                ]}
              />
              {total > pageSize && (
                <div className="mt-4 flex items-center justify-between text-sm">
                  <span className="text-slate-500">
                    Page {page} of {Math.max(1, Math.ceil(total / pageSize))}
                  </span>
                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                      Prev
                    </Button>
                    <Button variant="secondary" size="sm" disabled={page * pageSize >= total} onClick={() => setPage((p) => p + 1)}>
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </Card>
      </DashboardShell>
    </RequireAuth>
  );
}