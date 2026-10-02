import Link from "next/link";
import { BrandLogo } from "@/components/BrandLogo";

const columns = [
  {
    title: "Product",
    links: [
      { label: "Pricing", href: "/pricing" },
      { label: "Help Center", href: "/help" },
      { label: "Contact Us", href: "/contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Terms of Service", href: "/terms" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-xs">
            <BrandLogo />
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Professional quotes for cleaning businesses. Create, send, and track quotations in
              minutes.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-8 sm:gap-16">
            {columns.map((column) => (
              <nav key={column.title} aria-label={column.title}>
                <p className="text-sm font-semibold text-slate-900">{column.title}</p>
                <ul className="mt-3 space-y-2">
                  {column.links.map((link) => (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        className="text-sm text-slate-600 hover:text-brand-600 hover:underline"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
        </div>
        <div className="mt-10 border-t border-slate-200 pt-6 text-center text-xs text-slate-400">
          © {new Date().getFullYear()} QuoteFlow AI. All rights reserved.
        </div>
      </div>
    </footer>
  );
}