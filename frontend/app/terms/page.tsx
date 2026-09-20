import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-white">
      <SiteNav />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <h1 className="text-3xl font-extrabold text-slate-900">Terms of Service</h1>
        <p className="mt-2 text-sm text-slate-500">Last updated: September 13, 2026</p>

        <section className="mt-8 space-y-4 text-sm leading-6 text-slate-700">
          <h2 className="text-lg font-semibold text-slate-900">Using QuoteFlow AI</h2>
          <p>
            QuoteFlow AI provides software for creating, sending, and tracking quotations. You must
            be at least 18 years old and provide accurate account information.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">Plans & subscriptions</h2>
          <p>
            Free plans include a monthly quote allowance. Paid plans are billed through Stripe and
            renew automatically until cancelled. You may cancel at any time; access continues until
            the end of your billing period, then you are downgraded to the Free plan.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">Acceptable use</h2>
          <p>
            You agree not to misuse the service, attempt to access another user&apos;s data, exceed
            advertised limits, upload malicious files, or use the service for unlawful purposes.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">AI features</h2>
          <p>
            AI-generated text is provided on a best-effort basis and may contain errors. You are
            responsible for reviewing all quotes before sending them. Quote totals are computed by
            QuoteFlow AI, not by the AI model.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">No warranty</h2>
          <p>
            The service is provided &ldquo;as is&rdquo; without warranties of any kind. We are not
            liable for indirect or consequential damages arising from your use of the service.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">Termination</h2>
          <p>
            You may delete your account at any time. We may suspend accounts that violate these
            terms.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">Changes</h2>
          <p>
            We may update these terms. Continued use of the service after changes constitutes
            acceptance.
          </p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}