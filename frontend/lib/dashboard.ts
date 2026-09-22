import { CURRENCY_SYMBOLS } from "@/lib/format";
import type { CurrencyTotal, QuoteStats, QuoteStatus, SubscriptionInfo } from "@/types";

export const STATUS_ORDER: QuoteStatus[] = [
  "draft",
  "sent",
  "viewed",
  "accepted",
  "rejected",
  "expired",
  "cancelled",
];

export const CURRENCY_ORDER = ["USD", "CAD", "INR", "GBP", "AUD"] as const;

export interface CurrencyBucket {
  currency: string;
  label: string;
  isOther: boolean;
  currencySymbol: string;
  count: number;
  subtotal_minor: number;
  discount_minor: number;
  tax_minor: number;
  total_minor: number;
}

/** Group per-currency totals into known buckets + an "Other" aggregate. */
export function groupTotalsByCurrency(totals: CurrencyTotal[]): CurrencyBucket[] {
  const known: CurrencyBucket[] = CURRENCY_ORDER.map((code) => ({
    currency: code,
    label: code,
    isOther: false,
    currencySymbol: CURRENCY_SYMBOLS[code] ?? code,
    count: 0,
    subtotal_minor: 0,
    discount_minor: 0,
    tax_minor: 0,
    total_minor: 0,
  }));

  let other: CurrencyBucket = {
    currency: "__other__",
    label: "Other",
    isOther: true,
    currencySymbol: "",
    count: 0,
    subtotal_minor: 0,
    discount_minor: 0,
    tax_minor: 0,
    total_minor: 0,
  };

  for (const t of totals) {
    const bucket = known.find((k) => k.currency === t.currency);
    if (bucket) {
      bucket.count += t.count;
      bucket.subtotal_minor += t.subtotal_minor;
      bucket.discount_minor += t.discount_minor;
      bucket.tax_minor += t.tax_minor;
      bucket.total_minor += t.total_minor;
    } else {
      other.count += t.count;
      other.subtotal_minor += t.subtotal_minor;
      other.discount_minor += t.discount_minor;
      other.tax_minor += t.tax_minor;
      other.total_minor += t.total_minor;
    }
  }

  const buckets = known.filter((k) => k.count > 0);
  if (other.count > 0) buckets.push(other);
  return buckets;
}

/** Ordered list of the 7 quote statuses with their counts. */
export function statusCounts(stats: QuoteStats): { status: QuoteStatus; count: number }[] {
  return STATUS_ORDER.map((s) => ({ status: s, count: stats[s] ?? 0 }));
}

const EMPTY_HINTS: Record<QuoteStatus, string> = {
  draft: "No drafts — your next quote starts here.",
  sent: "Nothing sent yet — share a quote to start tracking it.",
  viewed: "No quotes have been viewed yet.",
  accepted: "No accepted quotes yet.",
  rejected: "No rejections — a clean record so far.",
  expired: "No expired quotes yet.",
  cancelled: "No cancelled quotes.",
};

/** Friendly message shown when a given status has a zero count. */
export function statusEmptyHint(status: QuoteStatus): string {
  return EMPTY_HINTS[status];
}

export interface UsageBreakdown {
  /** Quotes currently on the account (all statuses, never hard-deleted). */
  created: number;
  /** Quote creations tracked in the current billing period (incl. later deleted/duplicated). */
  used: number;
  /** Monthly plan cap; null when the plan is unlimited. */
  limit: number | null;
  /** True when the effective plan has no quote cap. */
  unlimited: boolean;
}

/**
 * Combine the on-account quote count, the period usage counter and the plan
 * cap so the plan card can show three clearly labeled numbers. The backend
 * usage counter counts every quote creation in the current period — including
 * quotes that were later deleted or duplicated — while the stats total counts
 * quotes still on the account, which explains "7 used but only 2 shown".
 */
export function usageBreakdown(sub: SubscriptionInfo, stats: QuoteStats): UsageBreakdown {
  return {
    created: stats.total,
    used: sub.quotes_used,
    limit: sub.quotes_limit,
    unlimited: sub.quotes_limit === null,
  };
}

/** True when a free-plan user has exceeded or hit their quote limit. */
export function isUpgradeWarningNeeded(sub: SubscriptionInfo): boolean {
  if (sub.plan !== "free") return false;
  if (sub.quotes_limit === null) return false;
  return sub.quotes_limit > 0 && sub.quotes_used >= sub.quotes_limit;
}

export interface DashboardFilters {
  q: string;
  status: QuoteStatus | "";
  currency: string;
  dateFrom: string;
  dateTo: string;
  page: number;
  pageSize: number;
}

/** Build the query-string for GET /api/quotes used by the dashboard list. */
export function buildQuotesQuery(f: DashboardFilters): string {
  const p = new URLSearchParams({
    page: String(f.page),
    page_size: String(f.pageSize),
  });
  if (f.q.trim()) p.set("q", f.q.trim());
  if (f.status) p.set("status", f.status);
  if (f.currency) p.set("currency", f.currency);
  if (f.dateFrom) p.set("date_from", f.dateFrom);
  if (f.dateTo) p.set("date_to", f.dateTo);
  return p.toString();
}
