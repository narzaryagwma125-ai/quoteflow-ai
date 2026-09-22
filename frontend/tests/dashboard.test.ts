import { describe, expect, it } from "vitest";
import {
  buildQuotesQuery,
  CURRENCY_ORDER,
  groupTotalsByCurrency,
  isUpgradeWarningNeeded,
  statusCounts,
  statusEmptyHint,
  STATUS_ORDER,
  usageBreakdown,
} from "@/lib/dashboard";
import { CURRENCY_SYMBOLS, formatMoney, formatMoneyWithCode } from "@/lib/format";
import type { CurrencyTotal, QuoteStats, SubscriptionInfo } from "@/types";

function total(currency: string, count = 1, total_minor = 10000): CurrencyTotal {
  return {
    currency,
    currency_symbol: CURRENCY_SYMBOLS[currency] ?? currency,
    count,
    subtotal_minor: total_minor,
    discount_minor: 0,
    tax_minor: 0,
    total_minor,
  };
}

describe("groupTotalsByCurrency", () => {
  it("returns no buckets for an empty stats payload", () => {
    expect(groupTotalsByCurrency([])).toEqual([]);
  });

  it("groups known currencies in USD, CAD, INR, GBP, AUD order and sums amounts", () => {
    const buckets = groupTotalsByCurrency([
      total("USD", 2, 25000),
      total("CAD", 1, 5000),
      total("INR", 3, 150000),
      total("GBP", 1, 6000),
      total("AUD", 1, 7000),
      total("USD", 1, 1000),
    ]);
    expect(buckets.map((b) => b.currency)).toEqual(["USD", "CAD", "INR", "GBP", "AUD"]);
    const usd = buckets.find((b) => b.currency === "USD");
    expect(usd).toMatchObject({ count: 3, total_minor: 26000 });
    expect(usd?.currencySymbol).toBe("$");
    expect(buckets.find((b) => b.currency === "CAD")?.currencySymbol).toBe("CA$");
    expect(buckets.find((b) => b.currency === "INR")?.currencySymbol).toBe("₹");
    expect(buckets.find((b) => b.currency === "GBP")?.currencySymbol).toBe("£");
    expect(buckets.find((b) => b.currency === "AUD")?.currencySymbol).toBe("A$");
  });

  it("rolls any unsupported currency into a single Other bucket", () => {
    const buckets = groupTotalsByCurrency([
      total("EUR", 1, 9000),
      total("CHF", 2, 4000),
    ]);
    expect(buckets).toHaveLength(1);
    const other = buckets[0];
    expect(other.isOther).toBe(true);
    expect(other.label).toBe("Other");
    expect(other.count).toBe(3);
    expect(other.total_minor).toBe(13000);
  });

  it("drops empty known buckets and appends Other after the known ones", () => {
    const other = total("EUR", 1, 7000);
    const buckets = groupTotalsByCurrency([other]);
    expect(buckets).toHaveLength(1);
    expect(buckets[0].isOther).toBe(true);
  });
});

describe("statusCounts", () => {
  it("returns all seven statuses in the dashboard order", () => {
    const stats: QuoteStats = {
      draft: 1,
      sent: 2,
      viewed: 0,
      accepted: 3,
      rejected: 0,
      expired: 0,
      cancelled: 1,
      total: 7,
      created_this_month: 7,
      totals_by_currency: [],
    };
    const counts = statusCounts(stats);
    expect(counts.map((c) => c.status)).toEqual(STATUS_ORDER);
    expect(counts).toEqual([
      { status: "draft", count: 1 },
      { status: "sent", count: 2 },
      { status: "viewed", count: 0 },
      { status: "accepted", count: 3 },
      { status: "rejected", count: 0 },
      { status: "expired", count: 0 },
      { status: "cancelled", count: 1 },
    ]);
  });
});

describe("isUpgradeWarningNeeded", () => {
  const free: SubscriptionInfo = {
    plan: "free",
    status: "free",
    current_period_start: null,
    current_period_end: null,
    cancel_at_period_end: false,
    quotes_used: 3,
    quotes_limit: 3,
    quotes_remaining: 0,
    ai_used: 0,
    ai_limit: 10,
    ai_remaining: 10,
    trial_active: false,
    trial_expired: true,
    trial_days_remaining: 0,
    trial_expires_at: null,
    trial_unlimited: false,
  };

  it("warns when the free quote limit is met", () => {
    expect(isUpgradeWarningNeeded(free)).toBe(true);
  });

  it("does not warn while under the free limit", () => {
    expect(isUpgradeWarningNeeded({ ...free, quotes_used: 2 })).toBe(false);
  });

  it("does not warn for paid plans even at the limit", () => {
    expect(
      isUpgradeWarningNeeded({ ...free, plan: "starter", status: "active", quotes_limit: 50, quotes_remaining: 47 }),
    ).toBe(false);
  });

  it("does not warn during the trial while under the trial limit", () => {
    expect(
      isUpgradeWarningNeeded({ ...free, trial_active: true, quotes_limit: 50, quotes_used: 10 }),
    ).toBe(false);
  });

  it("warns once the trial quote limit is met", () => {
    expect(
      isUpgradeWarningNeeded({ ...free, trial_active: true, quotes_limit: 50, quotes_used: 50, quotes_remaining: 0 }),
    ).toBe(true);
  });

  it("does not warn when the plan has an unlimited quote cap", () => {
    expect(
      isUpgradeWarningNeeded({ ...free, quotes_limit: null, quotes_remaining: null, quotes_used: 999 }),
    ).toBe(false);
  });
});

describe("buildQuotesQuery", () => {
  it("combines search, status, currency and date filters with pagination", () => {
    const qs = buildQuotesQuery({
      q: "acme",
      status: "sent",
      currency: "USD",
      dateFrom: "2026-09-01",
      dateTo: "2026-09-30",
      page: 2,
      pageSize: 10,
    });
    const params = new URLSearchParams(qs);
    expect(params.get("q")).toBe("acme");
    expect(params.get("status")).toBe("sent");
    expect(params.get("currency")).toBe("USD");
    expect(params.get("date_from")).toBe("2026-09-01");
    expect(params.get("date_to")).toBe("2026-09-30");
    expect(params.get("page")).toBe("2");
    expect(params.get("page_size")).toBe("10");
  });

  it("omits empty filters", () => {
    const qs = buildQuotesQuery({
      q: " \n",
      status: "",
      currency: "",
      dateFrom: "",
      dateTo: "",
      page: 1,
      pageSize: 5,
    });
    expect(qs).toBe("page=1&page_size=5");
  });
});

describe("currency order", () => {
  it("lists the supported currencies in stable order then others by design", () => {
    expect(CURRENCY_ORDER).toEqual(["USD", "CAD", "INR", "GBP", "AUD"]);
  });
});

describe("supported and unknown currency formatting", () => {
  it("formats Indian rupees, pounds and Australian dollars", () => {
    expect(formatMoney(150000, "INR")).toBe("₹1,500.00");
    expect(CURRENCY_SYMBOLS.INR).toBe("₹");
    expect(formatMoney(9000, "GBP")).toBe("£90.00");
    expect(CURRENCY_SYMBOLS.GBP).toBe("£");
    expect(formatMoney(9000, "AUD")).toBe("A$90.00");
    expect(CURRENCY_SYMBOLS.AUD).toBe("A$");
  });

  it("falls back to the ISO code for unknown currencies", () => {
    expect(formatMoney(9000, "EUR")).toBe("EUR 90.00");
  });
});

describe("formatMoneyWithCode", () => {
  it("puts a space between the amount and the ISO code", () => {
    expect(formatMoneyWithCode(50400, "USD")).toBe("$504.00 USD");
    expect(formatMoneyWithCode(16800, "INR")).toBe("₹168.00 INR");
    expect(formatMoneyWithCode(2530, "CAD")).toBe("CA$25.30 CAD");
    expect(formatMoneyWithCode(6000, "GBP")).toBe("£60.00 GBP");
    expect(formatMoneyWithCode(7000, "AUD")).toBe("A$70.00 AUD");
  });

  it("never concatenates the symbol directly onto the code", () => {
    const formatted = formatMoneyWithCode(25000);
    expect(formatted.endsWith("250.00USD")).toBe(false);
    expect(formatted).toMatch(/\d USD$/);
  });

  it("uppercases the code for mixed-case input", () => {
    expect(formatMoneyWithCode(1000, "usd")).toBe("$10.00 USD");
  });
});

describe("separate USD/INR totals", () => {
  it("keeps USD and INR in distinct buckets without summing them together", () => {
    const buckets = groupTotalsByCurrency([total("USD", 2, 25000), total("INR", 1, 150000)]);
    expect(buckets).toHaveLength(2);
    expect(buckets[0]).toMatchObject({ currency: "USD", count: 2, total_minor: 25000 });
    expect(buckets[1]).toMatchObject({ currency: "INR", count: 1, total_minor: 150000 });
    expect(buckets[0].total_minor + buckets[1].total_minor).not.toBe(buckets[0].total_minor);
  });
});

describe("statusEmptyHint", () => {
  it.each(STATUS_ORDER)("returns a non-empty hint for %s", (status) => {
    expect(statusEmptyHint(status).length).toBeGreaterThan(0);
  });
});

describe("usageBreakdown", () => {
  const sub = (over: Partial<SubscriptionInfo> = {}): SubscriptionInfo =>
  ({
    plan: "free",
    status: "free",
    current_period_start: null,
    current_period_end: null,
    cancel_at_period_end: false,
    quotes_used: 7,
    quotes_limit: 3,
    quotes_remaining: 0,
    ai_used: 0,
    ai_limit: 10,
    ai_remaining: 10,
    trial_active: false,
    trial_expired: true,
    trial_days_remaining: 0,
    trial_expires_at: null,
    trial_unlimited: false,
    ...over,
  } as SubscriptionInfo);

  const stats = (totalQuotes: number): QuoteStats => ({
    draft: 1,
    sent: 1,
    viewed: 0,
    accepted: 0,
    rejected: 0,
    expired: 0,
    cancelled: 0,
    total: totalQuotes,
    created_this_month: totalQuotes,
    totals_by_currency: [],
  });

  it("shows on-account count, period usage and plan cap separately", () => {
    expect(usageBreakdown(sub(), stats(2))).toEqual({
      created: 2,
      used: 7,
      limit: 3,
      unlimited: false,
    });
  });

  it("reveals which count drives the '7 used but only 2 shown' difference", () => {
    const u = usageBreakdown(sub(), stats(2));
    expect(u.used).toBeGreaterThan(u.created);
  });

  it("keeps the trial within starter-level limits rather than unlimited", () => {
    const u = usageBreakdown(sub({ trial_active: true, quotes_limit: 50 }), stats(5));
    expect(u.unlimited).toBe(false);
    expect(u.limit).toBe(50);
  });

  it("marks a plan with no quote cap as unlimited", () => {
    const u = usageBreakdown(sub({ plan: "business", quotes_limit: null, quotes_remaining: null }), stats(5));
    expect(u.unlimited).toBe(true);
    expect(u.limit).toBeNull();
  });
});