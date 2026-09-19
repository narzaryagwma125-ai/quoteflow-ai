import Link from "next/link";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <SiteNav />
      <main>
        <section className="mx-auto max-w-6xl px-4 py-20 text-center">
          <h1 className="mx-auto max-w-3xl text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl">
            Create professional cleaning quotes in minutes.
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
            QuoteFlow AI helps US and Canadian cleaning businesses build, send, and track
            polished quotations — with AI assistance and built-in security.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/signup">
              <button className="rounded-lg bg-brand-600 px-6 py-3 text-base font-semibold text-white hover:bg-brand-700">
                Start free
              </button>
            </Link>
            <Link href="/pricing">
              <button className="rounded-lg border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 hover:bg-slate-50">
                View pricing
              </button>
            </Link>
          </div>
        </section>

        <section className="bg-slate-50 py-16">
          <div className="mx-auto grid max-w-6xl gap-6 px-4 sm:grid-cols-3">
            {[
              ["Sendable quote links", "Share a secure link. Customers view, accept, or reject without an account."],
              ["AI-powered writing", "Generate descriptions, rewrites, and introductions with Gemini."],
              ["Professional PDFs", "Branded PDFs with your logo, tax handling, and clean pricing."],
            ].map(([title, body]) => (
              <div key={title} className="rounded-xl border border-slate-200 bg-white p-6">
                <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
                <p className="mt-2 text-sm text-slate-600">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-4 py-16 text-center">
          <h2 className="text-2xl font-bold text-slate-900">Ready to get started?</h2>
          <p className="mt-2 text-slate-600">Free plan: 3 quotes a month, no credit card.</p>
          <Link href="/signup" className="mt-6 inline-block">
            <button className="rounded-lg bg-brand-600 px-6 py-3 font-semibold text-white hover:bg-brand-700">
              Create your account
            </button>
          </Link>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}