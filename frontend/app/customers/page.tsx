"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { api, asList, asNumber, isRecord } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Customer } from "@/types";

export default function CustomersPage() {
  const [rows, setRows] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 20;

  const load = useCallback(async (p: number, search: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<Customer[] | { items: Customer[]; total?: number }>(
        `/customers?page=${p}&page_size=${pageSize}${search ? `&q=${encodeURIComponent(search)}` : ""}`,
      );
      const list = asList<Customer>(res);
      setRows(list);
      setTotal(
        isRecord(res) ? asNumber(res.total, list.length) : list.length,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customers.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(page, q);
  }, [load, page, q]);

  useEffect(() => {
    setPage(1);
  }, [q]);

  return (
    <RequireAuth>
      <DashboardShell>
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-slate-900">Customers</h1>
          <Link href="/customers/new">
            <Button>New customer</Button>
          </Link>
        </div>
        <Card>
          <div className="mb-4">
            <input
              aria-label="Search customers"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by name or email…"
              className="w-full max-w-sm rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </div>
          {error && <ErrorState message={error} />}
          {loading ? (
            <Loading />
          ) : (
            <>
              <DataTable
                rows={rows}
                onRowClick={(c) => (window.location.href = `/customers/${c.id}`)}
                emptyMessage="No customers yet."
                columns={[
                  { key: "name", header: "Name", render: (c) => <span className="font-medium">{c.name}</span> },
                  { key: "email", header: "Email", render: (c) => c.email || "—" },
                  { key: "phone", header: "Phone", render: (c) => c.phone || "—" },
                  { key: "quotes", header: "Quotes", render: (c) => c.quote_count ?? 0 },
                  { key: "created", header: "Added", render: (c) => formatDate(c.created_at) },
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