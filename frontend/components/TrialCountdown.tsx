"use client";

import { useEffect, useMemo, useState } from "react";
import { formatDate } from "@/lib/format";

type Props = {
  expiresAt: string | null | undefined;
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

export function TrialCountdown({ expiresAt }: Props) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const remaining = useMemo(() => remainingParts(expiresAt, now), [expiresAt, now]);
  if (!expiresAt || !remaining) return null;

  return (
    <div className="mt-3 rounded-xl border border-brand-200 bg-white/70 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Trial ends</p>
          <p className="mt-1 font-semibold text-brand-900">{formatDate(expiresAt)}</p>
        </div>
        <p className="font-mono text-sm font-extrabold text-brand-700">
          {remaining.totalSeconds <= 0
            ? "Trial expired"
            : `${remaining.days}d ${String(remaining.hours).padStart(2, "0")}h ${String(remaining.minutes).padStart(2, "0")}m ${String(remaining.seconds).padStart(2, "0")}s`}
        </p>
      </div>
    </div>
  );
}
