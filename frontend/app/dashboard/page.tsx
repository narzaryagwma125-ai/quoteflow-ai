"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { StatusBadge } from "@/components/StatusBadge";
import { CurrencyAmount } from "@/components/CurrencyAmount";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import type { QuoteFormPayload } from "@/components/QuoteForm";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { QuoteList } from "@/components/QuoteList";
import { api, apiBlob, asList, asNumber, isRecord, ApiError } from "@/lib/api";
import {
  buildQuotesQuery,
  CURRENCY_ORDER,
  groupTotalsByCurrency,
  isUpgradeWarningNeeded,
  statusCounts,
  statusEmptyHint,
  STATUS_ORDER,
  usageBreakdown,
  type CurrencyBucket,
} from "@/lib/dashboard";
import { minorToDollars } from "@/lib/format";
import { buildQuoteCreateBody } from "@/lib/quote";
import type {
  CurrencyCode,
  Quote,
  QuoteStats,
  QuoteStatus,
  SubscriptionInfo,
} from "@/types";

const PAGE_SIZE = 10;

export default function DashboardPage() {
  const [stats, setStats] = useState<QuoteStats | null>(null);
  const [sub, setSub] = useState<SubscriptionInfo | null>(null);
  const [rows, setRows] = useState<Quote[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [qInput, setQInput] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [status, setStatus] = useState<QuoteStatus | "">("");
  const [currency, setCurrency] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [statsLoading, setStatsLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Quote | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(qInput), 300);
    return () => clearTimeout(t);
  }, [qInput]);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const [s, sl] = await Promise.all([
        api<QuoteStats>("/quotes/stats"),
        api<SubscriptionInfo>("/billing/subscription"),
      ]);
      setStats(s);
      setSub(sl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard.");
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const qs = buildQuotesQuery({
        q: debouncedQ,
        status,
        currency,
        dateFrom,
        dateTo,
        page,
        pageSize: PAGE_SIZE,
      });
      const res = await api<unknown>(`/quotes?${qs}`);
      setRows(asList<Quote>(res, []));
      setTotal(isRecord(res) ? asNumber(res.total, 0) : 0);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quotes.");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, status, currency, dateFrom, dateTo, page]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadStats(), loadList()]);
  }, [loadStats, loadList]);

  const resetAndSet = (patch: () => void) => {
    setPage(1);
    patch();
  };

  const downloadPdf = async (q: Quote) => {
    setBusyId(q.id);
    setError(null);
    try {
      const blob = await apiBlob(`/quotes/${q.id}/generate-pdf`, { method: "POST" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `quote-${q.quote_number}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF download failed.");
    } finally {
      setBusyId(null);
    }
  };

  const downloadDocx = async (q: Quote) => {
    setBusyId(q.id);
    setError(null);
    try {
      const blob = await apiBlob(`/quotes/${q.id}/download-docx`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `quote-${q.quote_number}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "DOCX download failed.");
    } finally {
      setBusyId(null);
    }
  };

  const duplicate = async (q: Quote) => {
    setBusyId(q.id);
    setError(null);
    try {
      const payload: QuoteFormPayload = {
        customer_id: q.customer_id,
        issue_date: new Date().toISOString().slice(0, 10),
        expiry_date: null,
        currency: q.currency as CurrencyCode,
        discount: minorToDollars(q.discount_minor),
        notes: q.notes,
        terms: q.terms,
        items: q.items.map((it, idx) => ({
          description: it.description,
          quantity: it.quantity,
          unit: it.unit,
          unit_price: minorToDollars(it.unit_price_minor),
          sort_order: idx,
        })),
      };
      await api("/quotes", { method: "POST", body: JSON.stringify(buildQuoteCreateBody(payload)) });
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to duplicate quote.");
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setBusyId(target.id);
    setError(null);
    try {
      await api(`/quotes/${target.id}`, { method: "DELETE" });
      setDeleteTarget(null);
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete quote.");
      setDeleteTarget(null);
    } finally {
      setBusyId(null);
    }
  };

  const uploadTemplate = async (file: File | undefined) => {
    if (!file) return;
    setTemplateBusy(true);
    setError(null);
    setNotice(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/business-profile/template", {
        method: "POST",
        body: fd,
        credentials: "same-origin",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        let message = typeof body.detail === "string" ? body.detail : "Template upload failed.";
        if (res.status === 404) {
          message = "Create your business profile first, then upload a DOCX template from the Business page.";
        }
        if (res.status === 401) throw new ApiError(401, "Authentication required.");
        throw new Error(message);
      }
      setNotice("Custom DOCX template uploaded. It will be used for new quote downloads.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Template upload failed.");
    } finally {
      setTemplateBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const buckets: CurrencyBucket[] = stats ? groupTotalsByCurrency(stats.totals_by_currency) : [];
  const counts = stats ? statusCounts(stats) : [];
  const usage = sub && stats ? usageBreakdown(sub, stats) : null;
  const warnUpgrade = sub ? isUpgradeWarningNeeded(sub) : false;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <RequireAuth>
      <DashboardShell>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <div className="flex flex-wrap gap-2">
            <input
              ref={fileRef}
              type="file"
              accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="hidden"
              onChange={(e) => void uploadTemplate(e.target.files?.[0])}
            />
            <Button
              variant="secondary"
              loading={templateBusy}
              onClick={() => fileRef.current?.click()}
            >
              Upload DOCX Template
            </Button>
            <Link href="/quotes/new">
              <Button>+ Create New Quote</Button>
            </Link>
          </div>
        </div>

        {error && <div className="mb-4"><ErrorState message={error} onRetry={() => void refreshAll()} /></div>}
        {notice && !error && (
          <div className="mb-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">
            {notice}
          </div>
        )}

        {statsLoading || !stats ? (
          <Loading label="Loading dashboard…" />
        ) : (
          <div className="space-y-6">
            {buckets.length === 0 ? (
              <Card>
                <p className="text-sm text-slate-500">
                  No quotes yet.{" "}
                  <Link href="/quotes/new" className="text-brand-600 hover:underline">
                    Create your first quote
                  </Link>{" "}
                  to see your totals here.
                </p>
              </Card>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {buckets.map((b) => (
                  <MetricCard key={b.currency} bucket={b} />
                ))}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <Metric label="Total quotes" value={stats.total} />
              <Metric label="Accepted" value={stats.accepted} />
              <Metric label="Sent" value={stats.sent} />
              <Metric label="Created this month" value={stats.created_this_month} />
            </div>

            <div className="grid gap-6 lg:grid-cols-3">
              <Card title="Quotes by status" className="lg:col-span-2">
                {counts.every((c) => c.count === 0) ? (
                  <p className="text-sm text-slate-500">
                    No quotes yet — status distribution will appear here once you create one.
                  </p>
                ) : (
                  <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {counts.map((c) => (
                      <li key={c.status} className="rounded-lg border border-slate-100 px-3 py-2">
                        <div className="flex items-center justify-between">
                          <StatusBadge status={c.status} />
                          <span className="text-sm font-semibold text-slate-700">{c.count}</span>
                        </div>
                        {c.count === 0 && (
                          <p className="mt-1 text-xs italic text-slate-400">{statusEmptyHint(c.status)}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              {sub && (
                <Card title="Your plan">
                  <p className="flex items-center justify-between">
                    <span className="text-lg font-semibold capitalize">{sub.plan}</span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium capitalize text-slate-600">
                      {sub.status === "free" ? "Free plan" : sub.status}
                    </span>
                  </p>
                  <dl className="mt-4 space-y-3 text-sm">
                    <UsageRow
                      label="Total quotes created"
                      value={usage ? usage.created.toLocaleString() : "—"}
                    />
                    <PlanUsage
                      label="Usage this period"
                      used={sub.quotes_used}
                      limit={sub.quotes_limit}
                      unlimited={sub.quotes_limit === null}
                    />
                    <UsageRow
                      label="Plan limit"
                      value={usage ? (usage.unlimited ? "Unlimited" : String(usage.limit)) : "—"}
                    />
                    <PlanUsage
                      label="AI assists used"
                      used={sub.ai_used}
                      limit={sub.ai_limit}
                    />
                  </dl>
                  <p className="mt-3 text-xs text-slate-500">
                    Usage counts every quote created in the current billing period — including any you
                    later deleted or duplicated. It resets at the start of each month.
                  </p>
                  {warnUpgrade && (
                    <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                      You&apos;ve used all {sub.quotes_limit ?? 0} free quotes.{" "}
                      <Link href="/billing" className="font-medium underline">
                        Upgrade your plan
                      </Link>{" "}
                      to keep creating quotes.
                    </p>
                  )}
                  <Link href="/billing" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
                    Manage plan
                  </Link>
                </Card>
              )}
            </div>

            <Card
              title="Recent quotes"
              action={
                <Link href="/quotes">
                  <Button variant="ghost" size="sm">View all</Button>
                </Link>
              }
            >
              <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
                <div className="col-span-2 lg:col-span-1">
                  <Input
                    label="Search"
                    placeholder="Number or customer…"
                    value={qInput}
                    onChange={(e) => resetAndSet(() => setQInput(e.target.value))}
                  />
                </div>
                <Select
                  label="Status"
                  value={status}
                  onChange={(e) => resetAndSet(() => setStatus(e.target.value as QuoteStatus | ""))}
                >
                  <option value="">All statuses</option>
                  {STATUS_ORDER.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </Select>
                <Select
                  label="Currency"
                  value={currency}
                  onChange={(e) => resetAndSet(() => setCurrency(e.target.value))}
                >
                  <option value="">All currencies</option>
                  {CURRENCY_ORDER.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </Select>
                <Input
                  type="date"
                  label="From"
                  value={dateFrom}
                  onChange={(e) => resetAndSet(() => setDateFrom(e.target.value))}
                />
                <Input
                  type="date"
                  label="To"
                  value={dateTo}
                  onChange={(e) => resetAndSet(() => setDateTo(e.target.value))}
                />
              </div>

              {loading ? (
                <Loading />
              ) : rows.length === 0 ? (
                <p className="text-sm text-slate-500">
                  {total === 0
                    ? "No quotes yet. Create one to see it here."
                    : "No quotes match your search or filters."}
                </p>
              ) : (
                <>
                  <QuoteList
                    rows={rows}
                    busyId={busyId}
                    handlers={{
                      onDocx: (q) => void downloadDocx(q),
                      onPdf: (q) => void downloadPdf(q),
                      onDuplicate: (q) => void duplicate(q),
                      onDelete: (q) => setDeleteTarget(q),
                    }}
                  />

                  {total > PAGE_SIZE && (
                    <div className="mt-4 flex items-center justify-between text-sm">
                      <span className="text-slate-500">
                        Page {page} of {totalPages} · {total} quote{total === 1 ? "" : "s"}
                      </span>
                      <div className="flex gap-2">
                        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                          Prev
                        </Button>
                        <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
                          Next
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </Card>
          </div>
        )}

        <ConfirmDialog
          open={deleteTarget !== null}
          title="Delete quote"
          message={`Permanently delete quote ${deleteTarget?.quote_number ?? ""} and revoke its public link? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          loading={busyId !== null}
          onConfirm={() => void confirmDelete()}
          onCancel={() => setDeleteTarget(null)}
        />
      </DashboardShell>
    </RequireAuth>
  );
}

function MetricCard({ bucket }: { bucket: CurrencyBucket }) {
  const mixed = bucket.isOther;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {bucket.isOther ? "Total quoted (other)" : `Total quoted (${bucket.currency})`}
      </p>
      <p className="mt-1 text-2xl font-bold text-slate-900">
        {mixed ? (
          (bucket.total_minor / 100).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })
        ) : (
          <CurrencyAmount minor={bucket.total_minor} currency={bucket.currency} />
        )}
      </p>
      <p className="mt-1 text-xs text-slate-500">
        {bucket.count} quote{bucket.count === 1 ? "" : "s"}
        {mixed && " · mixed currencies not combined"}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
    </div>
  );
}

function UsageRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-slate-600">{label}:</dt>
      <dd className="font-medium text-slate-800">{value}</dd>
    </div>
  );
}

function PlanUsage({
  label,
  used,
  limit,
  unlimited = false,
}: {
  label: string;
  used: number;
  limit: number | null;
  unlimited?: boolean;
}) {
  const pct = limit != null && limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between">
        <dt className="text-slate-600">{label}:</dt>
        <dd className="text-slate-500">
          {unlimited || limit === null ? `${used} / Unlimited` : `${used} / ${limit}`}
        </dd>
      </div>
      {!unlimited && limit !== null && (
        <div className="h-2 rounded-full bg-slate-100">
          <div className="h-2 rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}