"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import type { Me } from "@/types";

const navLink = (active: boolean) =>
  `block rounded-lg px-3 py-2 text-sm font-medium ${
    active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
  }`;

export function SiteNav({ user }: { user?: Me | null }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const closeMobile = () => setOpen(false);
  const handleLogout = () =>
    void fetch("/api/auth/logout", { method: "POST" }).then(() => (window.location.href = "/login"));

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link href={user ? "/dashboard" : "/"} className="text-lg font-bold text-brand-600">
          QuoteFlow AI
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          <Link href="/pricing" className={navLink(pathname === "/pricing")}>
            Pricing
          </Link>
          <Link href="/help" className={navLink(pathname === "/help")}>
            Help
          </Link>
          <Link href="/contact" className={navLink(pathname === "/contact")}>
            Contact
          </Link>
          {user ? (
            <>
              <Link href="/quotes" className={navLink(pathname.startsWith("/quotes"))}>
                Quotes
              </Link>
              <Link href="/billing" className={navLink(pathname.startsWith("/billing"))}>
                Billing
              </Link>
              <Button size="sm" variant="ghost" onClick={handleLogout}>
                Log out
              </Button>
            </>
          ) : (
            <>
              <Link href="/login" className={navLink(pathname === "/login")}>
                Log in
              </Link>
              <Link href="/signup" className="ml-2">
                <Button size="sm">Start free</Button>
              </Link>
            </>
          )}
        </nav>

        <button
          type="button"
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden"
          aria-label="Toggle navigation menu"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((o) => !o)}
        >
          <svg
            aria-hidden
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            {open ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {open && (
        <nav
          id="mobile-nav"
          className="space-y-1 border-t border-slate-200 px-4 pb-4 pt-2 md:hidden"
          aria-label="Main"
        >
          <Link href="/pricing" className={navLink(pathname === "/pricing")} onClick={closeMobile}>
            Pricing
          </Link>
          <Link href="/help" className={navLink(pathname === "/help")} onClick={closeMobile}>
            Help
          </Link>
          <Link href="/contact" className={navLink(pathname === "/contact")} onClick={closeMobile}>
            Contact
          </Link>
          {user ? (
            <>
              <Link href="/quotes" className={navLink(pathname.startsWith("/quotes"))} onClick={closeMobile}>
                Quotes
              </Link>
              <Link href="/billing" className={navLink(pathname.startsWith("/billing"))} onClick={closeMobile}>
                Billing
              </Link>
              <Button size="sm" variant="ghost" className="w-full justify-start" onClick={handleLogout}>
                Log out
              </Button>
            </>
          ) : (
            <>
              <Link href="/login" className={navLink(pathname === "/login")} onClick={closeMobile}>
                Log in
              </Link>
              <div className="pt-1">
                <Link href="/signup" onClick={closeMobile}>
                  <Button size="sm" className="w-full">
                    Start free
                  </Button>
                </Link>
              </div>
            </>
          )}
        </nav>
      )}
    </header>
  );
}