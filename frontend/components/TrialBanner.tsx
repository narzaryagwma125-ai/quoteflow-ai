"use client";

import Link from "next/link";
import type { Me } from "@/types";
import { TrialCountdown } from "@/components/TrialCountdown";

export function TrialBanner({ user }: { user: Me | null }) {
  if (!user) {
    return null;
  }
  if (user.trial_active) {
    return (
      <div className="border-b border-brand-200 bg-brand-50 px-4 py-2 text-center text-sm text-brand-800">
        Free trial: {user.trial_days_remaining} day{user.trial_days_remaining === 1 ? "" : "s"} remaining — 200 quotes &amp; 200 AI assists included
        <div className="mx-auto max-w-md">
          <TrialCountdown expiresAt={user.trial_expires_at} />
        </div>
      </div>
    );
  }
  if (user.trial_expired) {
    return (
      <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-sm text-amber-800">
        Your free trial has ended. Please{" "}
        <Link href="/billing" className="font-semibold underline">
          choose a plan
        </Link>{" "}
        to keep creating quotes.
      </div>
    );
  }
  return null;
}