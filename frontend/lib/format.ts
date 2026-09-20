export const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$",
  CAD: "CA$",
  INR: "₹",
  GBP: "£",
  AUD: "A$",
};

export function formatMoney(minor: number, currency = "USD"): string {
  const code = (currency || "USD").toUpperCase();
  const symbol = CURRENCY_SYMBOLS[code] ?? (code !== "USD" ? `${code} ` : "$");
  const value = (minor / 100).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${symbol}${value}`;
}

/** Amount followed by its ISO code, e.g. "$504.00 USD". */
export function formatMoneyWithCode(minor: number, currency = "USD"): string {
  const code = (currency || "USD").toUpperCase();
  return `${formatMoney(minor, code)} ${code}`;
}

/** Parse a user-entered dollar string into minor units (validate max 2 decimals). */
export function toMinor(value: string | number | undefined): number | null {
  if (value === undefined || value === null || value === "") return null;
  const str = String(value).trim();
  if (!/^\d+(\.\d{1,2})?$/.test(str)) return null;
  return Math.round(parseFloat(str) * 100);
}

/** Convert minor units to a display string for an input field. */
export function minorToDollars(minor: number | undefined): string {
  if (minor === undefined || minor === null) return "";
  return (minor / 100).toFixed(2);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}

export function isValidPositiveQuantity(value: string): boolean {
  return /^\d+(\.\d{1,3})?$/.test(value.trim()) && parseFloat(value) > 0;
}