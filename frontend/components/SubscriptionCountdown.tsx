"use client";

import { useEffect, useMemo, useState } from "react";
import { formatDate } from "@/lib/format";

type Props = {
  periodEnd: string | null | undefined;
  cancelAtPeriodEnd?: boolean;
};

function remainingParts(target: string | null | undefined, now: number) {
  if (!target) return null;
  const end = new Date(target).getTime();
  if (!Number.isFinite(end)) return null;
  const diff = Math.max(0, end - now);
  const totalSeconds = Math.floor(diff / 1000);
  return {
    totalSeconds,
    days: Math.floor(totalSeconds / 86400),
    hours: Math.floor((totalSeconds % 86400) / 3600),
    minutes: Math.floor((totalSeconds % 3600) / 60),
    seconds: totalSeconds % 60,
  };
}

export function SubscriptionCountdown({ periodEnd, cancelAtPeriodEnd = false }: Props) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const remaining = useMemo(() => remainingParts(periodEnd, now), [periodEnd, now]);
  if (!periodEnd || !remaining) return null;

  const expired = remaining.totalSeconds <= 0;
  const label = cancelAtPeriodEnd ? "Access ends" : "Next billing date";

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-1 text-base font-bold text-slate-900">{formatDate(periodEnd)}</p>
        </div>
        <div className="text-right">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {cancelAtPeriodEnd ? "Time remaining" : "Time until renewal"}
          </p>
          <p className="mt-1 font-mono text-lg font-extrabold text-brand-700">
            {expired
              ? cancelAtPeriodEnd
                ? "Expired"
                : "Renewing now"
              : `${remaining.days}d ${String(remaining.hours).padStart(2, "0")}h ${String(remaining.minutes).padStart(2, "0")}m ${String(remaining.seconds).padStart(2, "0")}s`}
          </p>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {cancelAtPeriodEnd
          ? "Your paid access remains available until this date."
          : "The date is based on the subscription period reported by Stripe."}
      </p>
    </div>
  );
}
