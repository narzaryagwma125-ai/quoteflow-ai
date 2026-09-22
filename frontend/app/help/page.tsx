import Link from "next/link";
import { HelpFaq } from "@/components/HelpFaq";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";

const topics = [
  {
    href: "#getting-started",
    title: "Getting started",
    description: "Create your account and set up your business profile.",
  },
  {
    href: "#creating-a-quote",
    title: "Creating a quote",
    description: "Build a polished quote with services, dates, and discounts.",
  },
  {
    href: "#editing-a-quote",
    title: "Editing a quote",
    description: "Update details, items, and pricing after a quote is saved.",
  },
  {
    href: "#downloading-pdf",
    title: "Downloading PDF",
    description: "Export a branded, print-ready PDF of any quote.",
  },
  {
    href: "#subscription-and-billing",
    title: "Subscription & billing",
    description: "Plans, limits, trials, and how billing works.",
  },
  {
    href: "#email-verification",
    title: "Email verification",
    description: "Verify your address, resend links, and troubleshoot.",
  },
  {
    href: "#faq",
    title: "Frequently asked questions",
    description: "Quick answers to common questions.",
  },
];

const faqs = [
  {
    question: "Is there a free trial?",
    answer:
      "Yes. Every new account starts with a 5-day free trial that includes 200 quotes, unlimited customers, and AI assistance. When the trial ends you can continue on the Free plan (up to 3 quotes a month) or upgrade to Basic, Pro, or Business.",
  },
  {
    question: "Can I cancel my subscription anytime?",
    answer:
      "Absolutely. Go to the Billing page and cancel your subscription. You keep full access until the end of your current billing period, then your account is automatically downgraded to the Free plan.",
  },
  {
    question: "How are quote totals calculated?",
    answer:
      "Quote totals are always computed by QuoteFlow AI on the server — never by the AI model. Quantities, prices, discounts, and your configured tax rate are applied to produce the exact total on the quote and in the PDF.",
  },
  {
    question: "Can customers accept or decline a quote online?",
    answer:
      "Yes. Every quote has a secure public link. Customers can open the link, review the quote, and accept or decline it without needing an account. Updates sync back to your dashboard instantly.",
  },
  {
    question: "Is my payment information stored by QuoteFlow AI?",
    answer:
      "No. Subscriptions are processed by Razorpay, and we never store credit card numbers. Your card details go directly to Razorpay's PCI-compliant servers.",
  },
  {
    question: "How do I reset my password?",
    answer:
      "Use the 'Forgot password?' link on the login page and follow the instructions in the reset email. Reset links expire after 30 minutes for security — you can always request a new one.",
  },
];

function SectionHeader({ id, title }: { id: string; title: string }) {
  return (
    <h2 id={id} className="scroll-mt-6 text-xl font-bold text-slate-900">
      {title}
    </h2>
  );
}

export default function HelpPage() {
  return (
    <div className="min-h-screen bg-white">
      <SiteNav />
      <main className="mx-auto max-w-6xl px-4 py-12">
        <h1 className="text-3xl font-extrabold text-slate-900">Help Center</h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          Everything you need to get the most out of QuoteFlow AI. Can&apos;t find what you&apos;re
          looking for? <Link href="/contact" className="font-medium text-brand-600 hover:underline">Contact our support team</Link>.
        </p>

        <nav aria-label="Help topics" className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {topics.map((topic) => (
            <Link
              key={topic.href}
              href={topic.href}
              className="rounded-xl border border-slate-200 bg-white p-5 transition-colors hover:border-brand-500 hover:bg-brand-50/50"
            >
              <p className="text-sm font-semibold text-slate-900">{topic.title}</p>
              <p className="mt-1 text-sm text-slate-600">{topic.description}</p>
            </Link>
          ))}
        </nav>

        <div className="mt-12 space-y-10">
          <section className="space-y-3">
            <SectionHeader id="getting-started" title="Getting started" />
            <ol className="list-inside list-decimal space-y-2 text-sm leading-6 text-slate-700">
              <li>
                <span className="font-semibold text-slate-900">Create your account.</span> Sign up
                with your email address, then verify it using the link we send you.
              </li>
              <li>
                <span className="font-semibold text-slate-900">Complete your business profile.</span>{" "}
                From the Business tab, add your business name, address, currency (USD or CAD), and
                tax rate. This appears on every quote and PDF.
              </li>
              <li>
                <span className="font-semibold text-slate-900">Add your customers.</span> Save your
                cleaning clients in the Customers tab so you can quote them in seconds.
              </li>
              <li>
                <span className="font-semibold text-slate-900">Create your first quote.</span> Use
                the step-by-step guide below — you&apos;ll have a professional quote ready in minutes.
              </li>
            </ol>
          </section>

          <section className="space-y-3">
            <SectionHeader id="creating-a-quote" title="Creating a quote" />
            <div className="space-y-2 text-sm leading-6 text-slate-700">
              <p>
                Go to <span className="font-medium text-slate-900">Quotes → New quote</span> to get
                started. Choose a customer, set the issue and expiry dates, and pick a currency.
              </p>
              <p>
                Add one or more service items — a description, quantity, unit (for example{" "}
                <em>hr</em>), and unit price. You can apply an overall discount and add notes and
                terms that will appear on the delivered quote.
              </p>
              <p>
                Use the AI assist feature to generate or polish descriptions. The final total is
                always computed on the server and can never be altered by the AI.
              </p>
            </div>
          </section>

          <section className="space-y-3">
            <SectionHeader id="editing-a-quote" title="Editing a quote" />
            <div className="space-y-2 text-sm leading-6 text-slate-700">
              <p>
                Open any quote from the Quotes list and select <span className="font-medium text-slate-900">Edit</span>.
                You can update dates, items, pricing, discounts, notes, and terms at any time.
              </p>
              <p>
                Customers who have already been sent a shared link will always see the latest
                version of the quote, so you can revise a price and re-share the same link.
              </p>
            </div>
          </section>

          <section className="space-y-3">
            <SectionHeader id="downloading-pdf" title="Downloading PDF" />
            <div className="space-y-2 text-sm leading-6 text-slate-700">
              <p>
                Open a quote and click <span className="font-medium text-slate-900">Download PDF</span>.
                The PDF includes your business branding — name, logo, and details — plus every
                line item, discounts, taxes, and the final total.
              </p>
              <p>
                PDFs are generated server-side and are print-ready, so they look identical on every
                device and email client.
              </p>
            </div>
          </section>

          <section className="space-y-3">
            <SectionHeader id="subscription-and-billing" title="Subscription & billing" />
            <div className="space-y-2 text-sm leading-6 text-slate-700">
              <p>
                New accounts get a <span className="font-medium text-slate-900">5-day free trial</span>{" "}
                with 200 quotes and 200 AI assists. After the trial, choose from:
              </p>
              <ul className="list-inside list-disc space-y-1 pl-2">
                <li><span className="font-medium text-slate-900">Free</span> — up to 3 quotes/month.</li>
                <li><span className="font-medium text-slate-900">Basic</span> — up to 200 quotes/month.</li>
                <li><span className="font-medium text-slate-900">Business</span> — unlimited quotes.</li>
              </ul>
              <p>
                Upgrades happen in the Billing tab through secure Razorpay checkout. You can upgrade,
                cancel, or manage your payment method there — QuoteFlow AI never stores card
                details. Cancelling keeps your access until the end of the current billing period.
              </p>
            </div>
          </section>

          <section className="space-y-3">
            <SectionHeader id="email-verification" title="Email verification" />
            <div className="space-y-2 text-sm leading-6 text-slate-700">
              <p>
                After signing up, check your inbox (and spam folder) for a verification link. If the
                link has expired or you didn&apos;t receive it, request a new one from Settings.
              </p>
              <p>
                Verification is required once per account. If you&apos;re still having trouble,
                visit the contact page and we&apos;ll re-send it for you.
              </p>
            </div>
          </section>

          <section className="space-y-4">
            <SectionHeader id="faq" title="Frequently asked questions" />
            <HelpFaq items={faqs} />
          </section>

          <section className="rounded-xl border border-brand-200 bg-brand-50 p-6 text-center">
            <h2 className="text-lg font-bold text-slate-900">Still need help?</h2>
            <p className="mt-1 text-sm text-slate-600">
              Our support team typically replies within 1-2 business days.
            </p>
            <Link href="/contact" className="mt-4 inline-block">
              <span className="inline-flex items-center justify-center rounded-lg bg-brand-600 px-6 py-3 text-sm font-medium text-white hover:bg-brand-700">
                Contact support
              </span>
            </Link>
          </section>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}