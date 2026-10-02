import { describe, expect, it } from "vitest";
import { CURRENCY_SYMBOLS, formatDate, formatMoney, minorToDollars, toMinor } from "@/lib/format";

describe("formatMoney", () => {
  it("formats minor units with a USD symbol", () => {
    expect(formatMoney(25000)).toBe("$250.00");
    expect(formatMoney(1875, "USD")).toBe("$18.75");
    expect(formatMoney(5)).toBe("$0.05");
  });

  it("uses CAD symbol for Canadian dollars", () => {
    expect(formatMoney(8060, "CAD")).toBe("CA$80.60");
  });

  it("uses INR, GBP and AUD symbols for their currencies", () => {
    expect(formatMoney(150000, "INR")).toBe("₹1,500.00");
    expect(formatMoney(6000, "GBP")).toBe("£60.00");
    expect(formatMoney(7000, "AUD")).toBe("A$70.00");
  });

  it("falls back to the ISO code for unsupported currencies", () => {
    expect(formatMoney(9000, "EUR")).toBe("EUR 90.00");
  });

  it("handles zero", () => {
    expect(formatMoney(0)).toBe("$0.00");
  });
});

describe("toMinor", () => {
  it("converts dollar strings to minor units", () => {
    expect(toMinor("149.99")).toBe(14999);
    expect(toMinor("100")).toBe(10000);
    expect(toMinor(42.5)).toBe(4250);
  });

  it("rejects invalid input", () => {
    expect(toMinor("1.999")).toBeNull();
    expect(toMinor("abc")).toBeNull();
    expect(toMinor("-5")).toBeNull();
    expect(toMinor("")).toBeNull();
    expect(toMinor(undefined)).toBeNull();
  });

  it("rejects more than two decimals", () => {
    expect(toMinor("10.123")).toBeNull();
  });
});

describe("minorToDollars", () => {
  it("round-trips minor units", () => {
    expect(minorToDollars(4350)).toBe("43.50");
    expect(minorToDollars(undefined)).toBe("");
  });
});

describe("formatDate", () => {
  it("formats ISO dates", () => {
    const out = formatDate("2026-09-01");
    expect(typeof out).toBe("string");
    expect(out.length).toBeGreaterThan(2);
  });

  it("handles missing values", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
  });
});

describe("CURRENCY_SYMBOLS", () => {
  it("exposes all supported currencies", () => {
    expect(CURRENCY_SYMBOLS).toMatchObject({
      USD: "$",
      CAD: "CA$",
      INR: "₹",
      GBP: "£",
      AUD: "A$",
    });
  });
});