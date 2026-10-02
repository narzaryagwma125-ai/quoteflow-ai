import { formatMoney } from "@/lib/format";

export function CurrencyAmount({
  minor,
  currency,
  className = "",
}: {
  minor: number;
  currency?: string;
  className?: string;
}) {
  return <span className={`tabular-nums ${className}`}>{formatMoney(minor, currency)}</span>;
}