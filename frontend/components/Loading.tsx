export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-3 py-16 text-slate-500">
      <span aria-hidden className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      <span>{label}</span>
    </div>
  );
}