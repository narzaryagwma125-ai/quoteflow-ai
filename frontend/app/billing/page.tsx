"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { SubscriptionInfo } from "@/types";

export default function BillingPage() {
  const [sub, setSub] = useState<SubscriptionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setSub(await api<SubscriptionInfo>("/billing/subscription"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load billing.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const checkout = async (plan: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ url: string }>("/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ plan }),
      });
      window.location.href = res.url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start checkout.");
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    setBusy(true);
    setError(null);
    try {
      await api<{ cancel_at_period_end: boolean }>("/billing/cancel", { method: "POST" });
      setConfirmCancel(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <RequireAuth>
      <DashboardShell>
        <h1 className="mb-6 text-2xl font-bold text-slate-900">Billing</h1>
        {error && <ErrorState message={error} onRetry={() => void load()} />}
        {loading ? (
          <Loading />
        ) : sub ? (
          <>
            {sub.trial_active ? (
              <div className="mb-6 rounded-lg border border-brand-200 bg-brand-50 p-4 text-sm text-brand-800">
                <p className="font-semibold">
                  Free trial: {sub.trial_days_remaining} day{sub.trial_days_remaining === 1 ? "" : "s"} remaining — 50 quotes &amp; 50 AI assists included
                </p>
                <p className="mt-1 text-brand-700">
                  Your trial includes 50 quote creations and 50 AI assists. Choose a plan any time to keep the benefits after it ends.
                </p>
              </div>
            ) : sub.trial_expired ? (
              <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                <p className="font-semibold">Your free trial has ended. Please choose a plan.</p>
                <p className="mt-1 text-amber-700">
                  Your quotes and customers stay saved. The monthly quote limit now applies to new creations.
                </p>
                <div className="mt-3 flex flex-wrap gap-3">
                  <Button onClick={() => void checkout("starter")} loading={busy}>
                    Upgrade to Starter ($9/mo)
                  </Button>
                  <Button variant="secondary" onClick={() => void checkout("business")} loading={busy}>
                    Upgrade to Business ($19/mo)
                  </Button>
                </div>
              </div>
            ) : null}
            <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Current plan">
              <p className="text-lg font-semibold capitalize">{sub.plan}</p>
              <p className="text-sm text-slate-500">{sub.status}</p>
              {sub.current_period_end && (
                <p className="mt-2 text-sm text-slate-600">
                  {sub.cancel_at_period_end
                    ? `Access until ${formatDate(sub.current_period_end)}, then downgrade to Free.`
                    : `Renews ${formatDate(sub.current_period_end)}.`}
                </p>
              )}
              <dl className="mt-4 space-y-2 text-sm">
                <UsageRow
                  label="Quotes this month"
                  used={sub.quotes_used}
                  limit={sub.quotes_limit}
                  unlimited={sub.quotes_limit === null}
                />
                <UsageRow label="AI assists" used={sub.ai_used} limit={sub.ai_limit} />
              </dl>
            </Card>

            <Card title="Manage" action={sub.plan !== "free" ? <button className="text-sm text-brand-600 hover:underline" onClick={() => window.open("https://buy.stripe.com/", "_blank")}>Stripe dashboard</button> : undefined}>
              {sub.plan === "free" ? (
                <div className="space-y-3">
                  <p className="text-sm text-slate-600">Upgrade to unlock more monthly quotes and AI assists.</p>
                  <div className="flex flex-wrap gap-3">
                    <Button onClick={() => void checkout("starter")} loading={busy}>
                      Upgrade to Starter ($9/mo)
                    </Button>
                    <Button variant="secondary" onClick={() => void checkout("business")} loading={busy}>
                      Upgrade to Business ($19/mo)
                    </Button>
                  </div>
                </div>
              ) : (
                <div>
                  <p className="mb-3 text-sm text-slate-600">
                    Your subscription stays active until the end of your billing period.
                  </p>
                  <Button
                    variant="danger"
                    size="sm"
                    disabled={sub.cancel_at_period_end}
                    onClick={() => setConfirmCancel(true)}
                  >
                    {sub.cancel_at_period_end ? "Cancellation scheduled" : "Cancel subscription"}
                  </Button>
                </div>
              )}
            </Card>
          </div>
          </>
        ) : null}

        <ConfirmDialog
          open={confirmCancel}
          title="Cancel subscription"
          message="You'll keep access until the end of your billing period, then be downgraded to the Free plan. Continue?"
          confirmLabel="Cancel subscription"
          danger
          loading={busy}
          onConfirm={() => void cancel()}
          onCancel={() => setConfirmCancel(false)}
        />
      </DashboardShell>
    </RequireAuth>
  );
}

function UsageRow({
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
        <dt className="text-slate-600">{label}</dt>
        <dd className="text-slate-500">
          {unlimited || limit === null ? "Unlimited" : `${used} / ${limit}`}
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