"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { SiteNav } from "@/components/SiteNav";
import { Loading } from "@/components/Loading";
import { TrialBanner } from "@/components/TrialBanner";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();

  const links = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/business", label: "Business" },
    { href: "/customers", label: "Customers" },
    { href: "/quotes", label: "Quotes" },
    { href: "/billing", label: "Billing" },
    { href: "/settings", label: "Settings" },
  ];

  const item = (href: string, label: string) => (
    <Link
      key={href}
      href={href}
      className={`block rounded-lg px-3 py-2 text-sm font-medium ${
        pathname === href || pathname.startsWith(href + "/")
          ? "bg-brand-50 text-brand-700"
          : "text-slate-600 hover:bg-slate-100"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <>
      <SiteNav user={user} />
      <TrialBanner user={user} />
      <div className="mx-auto flex max-w-6xl gap-6 px-4 py-6">
        {loading && !user ? (
          <Loading />
        ) : (
          <>
            <aside className="hidden w-48 shrink-0 lg:block">
              <nav className="sticky top-6 space-y-1">
                {links.map((l) => item(l.href, l.label))}
                <button
                  onClick={logout}
                  className="block w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-red-600 hover:bg-red-50"
                >
                  Log out
                </button>
              </nav>
            </aside>
            <main className="min-w-0 min-h-0 flex-1">{children}</main>
          </>
        )}
      </div>
    </>
  );
}