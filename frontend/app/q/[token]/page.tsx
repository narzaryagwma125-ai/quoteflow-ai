"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { CurrencyAmount } from "@/components/CurrencyAmount";
import { StatusBadge } from "@/components/StatusBadge";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { api, apiBlob } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { PublicQuote } from "@/types";

export default function PublicQuotePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [quote, setQuote] = useState<PublicQuote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<"accept" | "reject" | null>(null);
  const [busy, setBusy] = useState(false);
  const [doneMessage, setDoneMessage] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  const fetchQuote = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<PublicQuote>(`/public/quotes/${encodeURIComponent(token)}`, {
        headers: {},
      });
      setQuote(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Quote unavailable.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void fetchQuote();
  }, [fetchQuote]);

  const respond = async (decision: "accept" | "reject") => {
    if (!name.trim()) {
      setError("Please enter your name.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const csrf = document.cookie
        .split("; ")
        .find((c) => c.startsWith("quoteflow_csrf="))
        ?.split("=")[1];
      const body = { name: name.trim(), email: email.trim() || null };
      const res = await api<{ message: string }>(
        `/public/quotes/${encodeURIComponent(token)}/${decision}`,
        {
          method: "POST",
          headers: { "X-CSRF-Token": csrf ?? "" },
          body: JSON.stringify(body),
        },
      );
      setDoneMessage(res.message);
      setConfirmAction(null);
      if (decision === "accept") {
        setQuote((q) => (q ? { ...q, status: "accepted" } : q));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record your response.");
    } finally {
      setBusy(false);
    }
  };

  const downloadAcceptedPdf = async () => {
    setBusy(true);
    setError(null);
    try {
      const blob = await apiBlob(`/public/quotes/${encodeURIComponent(token)}/pdf`);
      const filename = `${quote?.quote_number ?? "quote"}-Accepted.pdf`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF download failed.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <FullPage><Loading /></FullPage>;
  }
  if (error) {
    return <FullPage><ErrorState message={error} /></FullPage>;
  }
  if (!quote) {
    return <FullPage><ErrorState message="Quote not found." /></FullPage>;
  }

  return (
    <FullPage>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">{quote.business_name}</h1>
        <StatusBadge status={quote.status} />
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between text-sm text-slate-600">
          <p>
            Quote <span className="font-semibold text-slate-900">{quote.quote_number}</span>
          </p>
          <p>Issued {formatDate(quote.issue_date)}{quote.expiry_date ? ` · Valid until ${formatDate(quote.expiry_date)}` : ""}</p>
        </div>

        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <th className="px-2 py-2 font-semibold">Description</th>
              <th className="px-2 py-2 text-right font-semibold">Qty</th>
              <th className="px-2 py-2 text-right font-semibold">Unit</th>
              <th className="px-2 py-2 text-right font-semibold">Unit price</th>
              <th className="px-2 py-2 text-right font-semibold">Line total</th>
            </tr>
          </thead>
          <tbody>
            {quote.items.map((it, i) => (
              <tr key={i} className="border-b border-slate-100">
                <td className="px-2 py-2">{it.description}</td>
                <td className="px-2 py-2 text-right">{it.quantity}</td>
                <td className="px-2 py-2 text-right">{it.unit}</td>
                <td className="px-2 py-2 text-right"><CurrencyAmount minor={it.unit_price_minor} currency={quote.currency} /></td>
                <td className="px-2 py-2 text-right font-medium"><CurrencyAmount minor={it.line_total_minor} currency={quote.currency} /></td>
              </tr>
            ))}
          </tbody>
        </table>

        <dl className="mt-4 ml-auto max-w-xs space-y-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">Subtotal</dt>
            <dd><CurrencyAmount minor={quote.subtotal_minor} currency={quote.currency} /></dd>
          </div>
          {quote.discount_minor > 0 && (
            <div className="flex justify-between">
              <dt className="text-slate-500">Discount</dt>
              <dd>−<CurrencyAmount minor={quote.discount_minor} currency={quote.currency} /></dd>
            </div>
          )}
          {quote.tax_minor > 0 && (
            <div className="flex justify-between">
              <dt className="text-slate-500">Tax</dt>
              <dd><CurrencyAmount minor={quote.tax_minor} currency={quote.currency} /></dd>
            </div>
          )}
          <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold">
            <dt>Total</dt>
            <dd><CurrencyAmount minor={quote.total_minor} currency={quote.currency} /></dd>
          </div>
        </dl>

        {quote.notes && (
          <p className="mt-4 whitespace-pre-wrap text-sm text-slate-600">{quote.notes}</p>
        )}
        {quote.terms && (
          <p className="mt-2 whitespace-pre-wrap border-t border-slate-100 pt-2 text-xs text-slate-500">
            <span className="font-medium text-slate-600">Terms: </span>
            {quote.terms}
          </p>
        )}
      </Card>

      {quote.status === "accepted" ? (
        <div className="mt-6 rounded-xl border border-green-200 bg-green-50 p-6 text-center">
          <p className="mb-4 text-sm font-medium text-green-800">Quote accepted.</p>
          <Button loading={busy} onClick={() => void downloadAcceptedPdf()}>
            Download Accepted Quote PDF
          </Button>
        </div>
      ) : doneMessage ? (
        <div className="mt-6 rounded-lg border border-green-200 bg-green-50 p-4 text-center text-sm text-green-800">
          {doneMessage}
        </div>
      ) : quote.may_respond ? (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
          <p className="mb-3 text-center text-sm text-slate-600">
            Do you want to accept or reject this quote?
          </p>
          <div className="mx-auto max-w-sm space-y-3">
                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-slate-700">Your name</span>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Jane Smith"
                    aria-label="Your name"
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-slate-700">Email (optional)</span>
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="jane@example.com"
                    aria-label="Email (optional)"
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
                  />
                </label>
              </div>
              <div className="mt-4 flex justify-center gap-3">
                <Button onClick={() => setConfirmAction("accept")}>Accept quote</Button>
                <Button variant="danger" onClick={() => setConfirmAction("reject")}>
                  Reject quote
                </Button>
              </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmAction !== null}
        title={confirmAction === "accept" ? "Accept quote" : "Reject quote"}
        message={
          confirmAction === "accept"
            ? "Accepting this quote confirms you agree to the services and total above."
            : "Rejecting this quote confirms the services are not wanted."
        }
        confirmLabel={confirmAction === "accept" ? "Accept" : "Reject quote"}
        danger={confirmAction === "reject"}
        loading={busy}
        onConfirm={() => void respond(confirmAction === "accept" ? "accept" : "reject")}
        onCancel={() => setConfirmAction(null)}
      />
    </FullPage>
  );
}

function FullPage({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-3xl items-center px-4 text-lg font-bold text-brand-600">
          QuoteFlow AI
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-8">{children}</main>
      <footer className="mx-auto max-w-3xl px-4 pb-8 text-center text-xs text-slate-400">
        Powered by QuoteFlow AI
      </footer>
    </div>
  );
}