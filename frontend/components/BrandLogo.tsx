import Link from "next/link";

export function BrandLogo({ href = "/", className = "" }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={`inline-flex items-center gap-2.5 ${className}`} aria-label="QuoteFlow AI home">
      <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-blue-600 to-violet-600 shadow-sm">
        <svg viewBox="0 0 40 40" className="h-6 w-6 text-white" fill="none" aria-hidden="true">
          <path d="M11 8.5h13.2L29 13.3v18.2a2 2 0 0 1-2 2H11a2 2 0 0 1-2-2v-21a2 2 0 0 1 2-2Z" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
          <path d="M24 8.5v5h5" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
          <path d="M14 21h10M14 25.5h7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
          <path d="m29.8 6.4.9 2.5 2.5.9-2.5.9-.9 2.5-.9-2.5-2.5-.9 2.5-.9.9-2.5Z" fill="currentColor" />
        </svg>
      </span>
      <span className="text-xl font-extrabold tracking-tight text-slate-950">
        QuoteFlow <span className="text-brand-600">AI</span>
      </span>
    </Link>
  );
}
