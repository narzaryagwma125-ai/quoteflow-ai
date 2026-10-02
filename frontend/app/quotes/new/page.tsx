"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { QuoteForm, type QuoteFormPayload } from "@/components/QuoteForm";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { api, asList, asQuoteId, isRecord } from "@/lib/api";
import { buildQuoteCreateBody } from "@/lib/quote";
import type { BusinessProfile, CurrencyCode, Customer, QuoteResponse } from "@/types";

export default function NewQuotePage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [presetCustomer, setPresetCustomer] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const customerParam = new URLSearchParams(window.location.search).get("customer_id");
    if (customerParam) {
      setPresetCustomer(Number(customerParam));
    }
    const load = async () => {
      try {
        const [p, cs] = await Promise.all([
          api<BusinessProfile | null>("/business-profile").catch(() => null),
          api<Customer[] | { items: Customer[] }>("/customers?page=1&page_size=100"),
        ]);
        setProfile(p);
        setCustomers(asList<Customer>(cs));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const save = async (payload: QuoteFormPayload) => {
    const res = await api<QuoteResponse>("/quotes", {
      method: "POST",
      body: JSON.stringify(buildQuoteCreateBody(payload)),
    });
    router.push(`/quotes/${asQuoteId(res)}`);
  };

  const taxRate = profile?.tax_rate_unconfigured ? "0" : profile?.tax_rate_percent ?? "0";

  if (loading) {
    return (
      <RequireAuth><DashboardShell><Loading /></DashboardShell></RequireAuth>
    );
  }

  return (
    <RequireAuth>
      <DashboardShell>
        <h1 className="mb-6 text-2xl font-bold text-slate-900">New quote</h1>
        {error && <ErrorState message={error} />}
        {profile && profile.tax_rate_unconfigured && (
          <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Your tax rate isn&apos;t configured yet. Tax will be 0% until you set it in{" "}
            <Link href="/business" className="font-medium underline">Business profile</Link>.
          </p>
        )}
        {!profile ? (
          <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Complete your{" "}
            <Link href="/business" className="font-medium underline">business profile</Link> to brand your quotes.
          </p>
        ) : null}
        <QuoteForm
          customers={customers.map((c) => ({ id: c.id, name: c.name }))}
          defaultValues={{
            customer_id: presetCustomer ? Number(presetCustomer) : undefined,
            currency: (profile?.currency as CurrencyCode) ?? "INR",
            issue_date: new Date().toISOString().slice(0, 10),
          }}
          taxRatePercent={taxRate}
          businessName={profile?.business_name ?? ""}
          onSave={save}
        />
      </DashboardShell>
    </RequireAuth>
  );
}