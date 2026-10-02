"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { QuoteForm, type QuoteFormPayload } from "@/components/QuoteForm";
import { CurrencyAmount } from "@/components/CurrencyAmount";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { api, apiBlob, asList, isRecord, ApiError } from "@/lib/api";
import { buildQuoteUpdateBody } from "@/lib/quote";
import { formatDate } from "@/lib/format";
import type { BusinessProfile, Customer, Quote, QuoteResponse } from "@/types";

export default function QuoteDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadFailure, setLoadFailure] = useState<{ status: number; message: string } | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<"cancel" | "delete" | null>(null);

  const normalizeQuote = useCallback((res: unknown): Quote => {
    const r = res as { quote?: unknown };
    return isRecord(r) && isRecord(r.quote) ? (r.quote as unknown as Quote) : (r as unknown as Quote);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setLoadFailure(null);
    try {
      const q = await api<QuoteResponse | Quote>(`/quotes/${id}`);
      setQuote(normalizeQuote(q));
      setLink(null);
      const [cs, p] = await Promise.all([
        api<unknown>("/customers?page_size=100").catch(() => []),
        api<BusinessProfile>("/business-profile").catch(() => null),
      ]);
      setCustomers(asList<Customer>(cs));
      setProfile(p);
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      const message = err instanceof Error ? err.message : "Failed to load quote.";
      setLoadFailure({ status, message });
    } finally {
      setLoading(false);
    }
  }, [id, normalizeQuote]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("edit") === "1"
    ) {
      setEditing(true);
    }
  }, []);

  const save = async (payload: QuoteFormPayload) => {
    setSaving(true);
    setError(null);
    try {
      const res = await api<QuoteResponse | Quote>(`/quotes/${id}`, {
        method: "PUT",
        body: JSON.stringify(buildQuoteUpdateBody(payload)),
      });
      setQuote(normalizeQuote(res));
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save quote.");
      throw err;
    } finally {
      setSaving(false);
    }
  };

  const send = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await api<QuoteResponse>(`/quotes/${id}/send`, { method: "POST" });
      setQuote(res.quote);
      const href = res.public_link ?? "";
      setLink(href);
      try {
        await navigator.clipboard.writeText(href);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        setCopied(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send quote.");
    } finally {
      setSaving(false);
    }
  };

  const revoke = async () => {
    try {
      const res = await api<QuoteResponse | Quote>(`/quotes/${id}/revoke-link`, { method: "POST" });
      setQuote(normalizeQuote(res));
      setLink(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke link.");
    }
  };

  const copyLink = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await api<QuoteResponse>(`/quotes/${id}/copy-link`, { method: "POST" });
      setQuote(res.quote);
      setLink(res.public_link ?? null);
      try {
        await navigator.clipboard.writeText(res.public_link ?? "");
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        setCopied(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to copy link.");
    } finally {
      setSaving(false);
    }
  };

  const downloadPdf = async () => {
    try {
      const blob = await apiBlob(`/quotes/${id}/generate-pdf`, { method: "POST" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `quote-${quote?.quote_number ?? id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF download failed.");
    }
  };

  const doConfirm = async () => {
    try {
      if (confirmAction === "cancel") {
        const res = await api<QuoteResponse | Quote>(`/quotes/${id}/cancel`, { method: "POST" });
        setQuote(normalizeQuote(res));
      } else if (confirmAction === "delete") {
        await api(`/quotes/${id}`, { method: "DELETE" });
        router.push("/quotes");
        return;
      }
      setConfirmOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
      setConfirmOpen(false);
    }
  };

  if (loading) {
    return (
      <RequireAuth><DashboardShell><Loading /></DashboardShell></RequireAuth>
    );
  }

  if (loadFailure) {
    const isAuth = loadFailure.status === 401;
    const isNotFound = loadFailure.status === 404;
    return (
      <RequireAuth>
        <DashboardShell>
          <ErrorState
            message={
              isAuth
                ? "Your session has expired. Please sign in again."
                : isNotFound
                  ? "Quote not found."
                  : loadFailure.message
            }
            onRetry={isAuth ? undefined : () => void load()}
          />
          {isAuth && (
            <a
              href="/login"
              className="mt-3 inline-block rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Sign in
            </a>
          )}
        </DashboardShell>
      </RequireAuth>
    );
  }

  const q = quote;
  const scheduleExpired = q?.expiry_date && new Date(q.expiry_date) < new Date();
  return (
    <RequireAuth>
      <DashboardShell>
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}
        {q && (
          <>
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Quote {q.quote_number}</h1>
                <p className="text-sm text-slate-500">
                  {q.customer_name || "No customer"} · Issued {formatDate(q.issue_date)}
                  {q.expiry_date ? ` · Expires ${formatDate(q.expiry_date)}` : ""}
                  {scheduleExpired && q.status === "sent" ? " · (expired)" : ""}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <StatusBadge status={q.status} />
                {!editing && (
                  <>
                    <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                      Edit
                    </Button>
                    {q.status !== "cancelled" && (
                      <Button variant="secondary" size="sm" onClick={() => void downloadPdf()}>
                        Download PDF
                      </Button>
                    )}
                    {(q.status === "draft" || q.status === "viewed") && (
                      <Button size="sm" loading={saving} onClick={() => void send()}>
                        Send link
                      </Button>
                    )}
                    {q.has_public_link && (
                      <Button variant="secondary" size="sm" loading={saving} onClick={() => void copyLink()}>
                        Copy link
                      </Button>
                    )}
                    {q.has_public_link && (
                      <Button variant="ghost" size="sm" onClick={() => void revoke()}>
                        Revoke link
                      </Button>
                    )}
                    {q.status !== "cancelled" && (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => {
                          setConfirmAction("cancel");
                          setConfirmOpen(true);
                        }}
                      >
                        Cancel quote
                      </Button>
                    )}
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        setConfirmAction("delete");
                        setConfirmOpen(true);
                      }}
                    >
                      Delete
                    </Button>
                  </>
                )}
              </div>
            </div>

            {editing ? (
              <QuoteForm
                initial={q}
                customers={customers.map((c) => ({ id: c.id, name: c.name }))}
                taxRatePercent={profile?.tax_rate_unconfigured ? "0" : profile?.tax_rate_percent ?? "0"}
                businessName={profile?.business_name ?? ""}
                onSave={save}
                onCancel={() => setEditing(false)}
              />
            ) : (
              <>
                {link && (
                  <div className="mb-6 rounded-lg border border-green-200 bg-green-50 p-4 text-sm">
                    <p className="mb-1 font-medium text-green-800">
                      {copied ? "Link copied to clipboard!" : "Public link"}
                    </p>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 truncate rounded bg-white px-2 py-1 text-green-800">{link}</code>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          void navigator.clipboard.writeText(link ?? "");
                          setCopied(true);
                          setTimeout(() => setCopied(false), 2000);
                        }}
                      >
                        {copied ? "Copied!" : "Copy"}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setLink(null)}>
                        Dismiss
                      </Button>
                    </div>
                  </div>
                )}

                <Card title="Line items">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                        <th className="px-2 py-2 font-semibold">Description</th>
                        <th className="px-2 py-2 text-right font-semibold">Qty</th>
                        <th className="px-2 py-2 text-right font-semibold">Unit price</th>
                        <th className="px-2 py-2 text-right font-semibold">Line total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {q.items.map((it) => (
                        <tr key={it.id ?? it.sort_order} className="border-b border-slate-100">
                          <td className="px-2 py-2">
                            <p>{it.description}</p>
                            {it.unit && <p className="text-xs text-slate-500">{it.unit}</p>}
                          </td>
                          <td className="px-2 py-2 text-right">{it.quantity}</td>
                          <td className="px-2 py-2 text-right"><CurrencyAmount minor={it.unit_price_minor} currency={q.currency} /></td>
                          <td className="px-2 py-2 text-right font-medium"><CurrencyAmount minor={it.line_total_minor} currency={q.currency} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <dl className="mt-4 ml-auto max-w-xs space-y-1 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Subtotal</dt>
                      <dd><CurrencyAmount minor={q.subtotal_minor} currency={q.currency} /></dd>
                    </div>
                    {q.discount_minor > 0 && (
                      <div className="flex justify-between">
                        <dt className="text-slate-500">Discount</dt>
                        <dd>−<CurrencyAmount minor={q.discount_minor} currency={q.currency} /></dd>
                      </div>
                    )}
                    {q.tax_minor > 0 && (
                      <div className="flex justify-between">
                        <dt className="text-slate-500">Tax ({q.breakdown?.tax_rate_percent}%)</dt>
                        <dd><CurrencyAmount minor={q.tax_minor} currency={q.currency} /></dd>
                      </div>
                    )}
                    <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold">
                      <dt>Total</dt>
                      <dd><CurrencyAmount minor={q.total_minor} currency={q.currency} /></dd>
                    </div>
                  </dl>
                </Card>

                {(q.notes || q.terms) && (
                  <Card title="Terms & notes">
                    {q.terms && (
                      <p className="mb-2 text-sm text-slate-700">
                        <span className="font-medium">Terms: </span>
                        <span className="whitespace-pre-wrap">{q.terms}</span>
                      </p>
                    )}
                    {q.notes && (
                      <p className="text-sm text-slate-700 whitespace-pre-wrap">
                        <span className="font-medium">Notes: </span>
                        {q.notes}
                      </p>
                    )}
                  </Card>
                )}
              </>
            )}

            <ConfirmDialog
              open={confirmOpen}
              title={confirmAction === "delete" ? "Delete quote" : "Cancel quote"}
              message={
                confirmAction === "delete"
                  ? "Permanently delete this quote and revoke its public link? This cannot be undone."
                  : "Mark this quote as cancelled? Its public link will be revoked."
              }
              confirmLabel={confirmAction === "delete" ? "Delete" : "Cancel quote"}
              danger
              loading={saving}
              onConfirm={doConfirm}
              onCancel={() => setConfirmOpen(false)}
            />
          </>
        )}
      </DashboardShell>
    </RequireAuth>
  );
}