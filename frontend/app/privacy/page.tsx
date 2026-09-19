import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-white">
      <SiteNav />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <h1 className="text-3xl font-extrabold text-slate-900">Privacy Policy</h1>
        <p className="mt-2 text-sm text-slate-500">Last updated: September 13, 2026</p>

        <section className="mt-8 space-y-4 text-sm leading-6 text-slate-700">
          <h2 className="text-lg font-semibold text-slate-900">What we collect</h2>
          <p>
            We collect the information you provide to create your account (email address, password)
            and to operate the service (business profile, customers, quotes, and billing records).
          </p>

          <h2 className="text-lg font-semibold text-slate-900">How we use it</h2>
          <p>
            Your data is used solely to provide QuoteFlow AI: creating and delivering quotes, PDF
            generation, AI-assisted writing (sent to our AI provider as text only), billing, and
            customer support. We never sell your personal data.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">AI assistance</h2>
          <p>
            Text you choose to generate or rewrite with AI is sent to a third-party AI model. Do not
            include sensitive personal information in those prompts. Quote amounts are computed by
            QuoteFlow AI on the server and are never derived from the AI model.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">Payments</h2>
          <p>
            Subscriptions are processed by Stripe. We do not store credit card numbers. Stripe&apos;s
            privacy policy governs the handling of your payment information.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">Security</h2>
          <p>
            Passwords are stored using Argon2id hashing. Session tokens and one-time links are stored
            only as cryptographic hashes. Connections are encrypted in transit.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">Retention & deletion</h2>
          <p>
            You can delete your account at any time from Settings, which permanently removes your
            account, customers, quotes, and personal data. Required billing records may be retained
            as permitted by law.
          </p>

          <h2 className="text-lg font-semibold text-slate-900">Contact</h2>
          <p>Questions about this policy? Contact support@quoteflow.example</p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}