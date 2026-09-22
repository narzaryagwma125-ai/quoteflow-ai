import Link from "next/link";
import { BrandLogo } from "@/components/BrandLogo";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";

const benefits = [
  ["AI quote writing", "Turn a few project details into polished descriptions, introductions, and customer-ready wording in seconds."],
  ["Professional PDFs", "Create clean, branded quotations with your business details, pricing, taxes, and logo."],
  ["Secure quote links", "Send one simple link so customers can review, accept, or reject a quote without creating an account."],
  ["Customer management", "Keep customers, projects, communication, and quote history organized in one workspace."],
  ["Business insights", "See quote activity and usage so you can understand what is moving through your sales pipeline."],
  ["Built for growth", "Start small, then move to Pro or Business when you need higher limits, advanced tools, and more scale."],
];

const steps = [
  ["01", "Add your business", "Set your business details, branding, currency, and customer information once."],
  ["02", "Build a quote", "Enter the job details and let QuoteFlow AI help you write a professional proposal."],
  ["03", "Send and track", "Download a PDF or share a secure link and keep the quote history in your dashboard."],
];

const plans = [
  { name: "Basic", price: "$6", description: "For freelancers and small businesses", features: ["200 quotes/month", "200 AI assists/month", "Unlimited customers", "Secure quote links"], href: "/signup?plan=starter" },
  { name: "Pro", price: "$12", description: "For businesses ready to scale", features: ["1,000 quotes/month", "1,000 AI assists/month", "Advanced dashboard", "Everything in Basic"], href: "/signup?plan=pro", popular: true },
  { name: "Business", price: "$24", description: "For teams and high-volume work", features: ["Unlimited quotes", "Unlimited AI assists", "Unlimited customers", "Priority support"], href: "/signup?plan=business" },
];

function Check() {
  return <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-emerald-700">✓</span>;
}

export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-hidden bg-white text-slate-900">
      <SiteNav />
      <main>
        <section className="relative border-b border-slate-100 bg-gradient-to-b from-indigo-50/70 via-white to-white">
          <div className="pointer-events-none absolute -left-24 top-12 h-72 w-72 rounded-full bg-indigo-200/30 blur-3xl" />
          <div className="pointer-events-none absolute -right-24 top-20 h-80 w-80 rounded-full bg-blue-200/30 blur-3xl" />
          <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:px-8 lg:py-24">
            <div>
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-white px-3 py-1.5 text-sm font-semibold text-indigo-700 shadow-sm">
                <span className="h-2 w-2 rounded-full bg-emerald-500" /> AI-powered quoting for modern businesses
              </div>
              <h1 className="max-w-3xl text-4xl font-black leading-tight tracking-tight text-slate-950 sm:text-5xl lg:text-6xl">
                Create professional quotes <span className="text-brand-600">faster with AI.</span>
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
                QuoteFlow AI helps service businesses create polished quotations, manage customers, send secure quote links, and turn more work into revenue — all from one simple workspace.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href="/signup" className="rounded-xl bg-brand-600 px-6 py-3.5 text-center font-bold text-white shadow-lg shadow-indigo-200 transition hover:bg-brand-700">
                  Start free trial →
                </Link>
                <Link href="/pricing" className="rounded-xl border border-slate-300 bg-white px-6 py-3.5 text-center font-bold text-slate-700 transition hover:border-brand-300 hover:text-brand-700">
                  See pricing
                </Link>
              </div>
              <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-500">
                <span>✓ 5-day free trial</span><span>✓ No credit card to start</span><span>✓ Cancel anytime</span>
              </div>
            </div>

            <div className="relative mx-auto w-full max-w-xl">
              <div className="absolute -inset-5 rounded-[2rem] bg-gradient-to-r from-indigo-200/40 to-blue-200/40 blur-2xl" />
              <div className="relative rounded-3xl border border-slate-200 bg-white p-3 shadow-2xl shadow-slate-200/80">
                <div className="flex items-center gap-2 border-b border-slate-100 px-3 pb-3">
                  <BrandLogo className="scale-90 origin-left" />
                  <span className="ml-auto rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">Dashboard</span>
                </div>
                <div className="grid gap-3 p-3 sm:grid-cols-3">
                  {[['124', 'Total quotes'], ['86', 'AI assists'], ['48', 'Customers']].map(([value, label]) => (
                    <div key={label} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                      <p className="text-2xl font-extrabold text-slate-900">{value}</p>
                      <p className="mt-1 text-xs text-slate-500">{label}</p>
                    </div>
                  ))}
                </div>
                <div className="grid gap-3 p-3 pt-0 sm:grid-cols-[1.2fr_.8fr]">
                  <div className="rounded-xl border border-slate-100 p-4">
                    <div className="flex items-center justify-between"><p className="font-bold">Quote activity</p><span className="text-xs text-emerald-600">+18%</span></div>
                    <div className="mt-5 flex h-32 items-end gap-2">
                      {[35, 48, 42, 68, 58, 82, 94, 76, 108, 118].map((h, i) => <span key={i} className="flex-1 rounded-t-md bg-gradient-to-t from-indigo-600 to-blue-400" style={{ height: `${h}px` }} />)}
                    </div>
                  </div>
                  <div className="rounded-xl border border-slate-100 p-4">
                    <p className="font-bold">Recent quotes</p>
                    <div className="mt-4 space-y-3 text-xs">
                      {['Website redesign · ₹45,000', 'Office cleaning · ₹12,500', 'SEO package · ₹8,900'].map((x) => <div key={x} className="rounded-lg bg-slate-50 p-2.5 text-slate-600">{x}</div>)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-slate-100 bg-white py-10">
          <div className="mx-auto grid max-w-7xl gap-4 px-4 sm:px-6 md:grid-cols-3 lg:px-8">
            {[['Save time', 'Spend less time writing repetitive quotations.'], ['Look professional', 'Send consistent, branded quotes that build trust.'], ['Close work faster', 'Make it easier for customers to review and respond.']].map(([title, body]) => (
              <div key={title} className="flex items-start gap-4 rounded-2xl border border-slate-100 bg-slate-50/70 p-5">
                <Check /><div><h2 className="font-bold">{title}</h2><p className="mt-1 text-sm leading-6 text-slate-600">{body}</p></div>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-bold uppercase tracking-wider text-brand-600">Everything in one place</p>
            <h2 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">More than a quote generator</h2>
            <p className="mt-4 text-slate-600">QuoteFlow AI combines quoting, customer management, sharing, and AI assistance so you can spend more time doing the work that grows your business.</p>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {benefits.map(([title, body], i) => (
              <div key={title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-50 text-lg font-black text-brand-600">{['✦','▣','↗','♙','◫','∞'][i]}</div>
                <h3 className="mt-5 text-lg font-bold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-slate-50 py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="grid gap-12 lg:grid-cols-[.8fr_1.2fr] lg:items-center">
              <div>
                <p className="text-sm font-bold uppercase tracking-wider text-brand-600">Simple workflow</p>
                <h2 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">From idea to professional quote in minutes.</h2>
                <p className="mt-4 leading-7 text-slate-600">No complicated sales software. Add the job, build the quote, and send it to your customer.</p>
                <Link href="/signup" className="mt-7 inline-flex rounded-xl bg-slate-900 px-5 py-3 font-bold text-white hover:bg-slate-800">Try QuoteFlow AI free</Link>
              </div>
              <div className="space-y-4">
                {steps.map(([num, title, body]) => (
                  <div key={num} className="flex gap-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-50 font-extrabold text-brand-600">{num}</span>
                    <div><h3 className="font-bold">{title}</h3><p className="mt-1 text-sm leading-6 text-slate-600">{body}</p></div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="pricing" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-bold uppercase tracking-wider text-brand-600">Simple pricing</p>
            <h2 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Choose the plan that fits your business</h2>
            <p className="mt-4 text-slate-600">Start free. Upgrade when you need more capacity. Secure checkout is powered by Razorpay.</p>
          </div>
          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {plans.map((plan) => (
              <div key={plan.name} className={`relative flex flex-col rounded-3xl border p-7 ${plan.popular ? 'border-brand-500 bg-indigo-50/50 shadow-xl shadow-indigo-100' : 'border-slate-200 bg-white shadow-sm'}`}>
                {plan.popular && <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-600 px-4 py-1 text-xs font-bold text-white">Most popular</span>}
                <h3 className="text-xl font-extrabold">{plan.name}</h3>
                <p className="mt-1 text-sm text-slate-500">{plan.description}</p>
                <div className="mt-6"><span className="text-4xl font-black">{plan.price}</span> <span className="text-sm text-slate-500">/month</span></div>
                <ul className="mt-6 flex-1 space-y-3 text-sm text-slate-700">{plan.features.map((feature) => <li key={feature} className="flex gap-2"><Check />{feature}</li>)}</ul>
                <Link href={plan.href} className={`mt-7 rounded-xl px-5 py-3 text-center font-bold ${plan.popular ? 'bg-brand-600 text-white hover:bg-brand-700' : 'border border-slate-300 text-slate-800 hover:border-brand-400 hover:text-brand-700'}`}>Get {plan.name}</Link>
              </div>
            ))}
          </div>
          <p className="mt-5 text-center text-xs text-slate-500">Prices shown in INR. International card payments depend on your Razorpay account and enabled payment methods.</p>
        </section>

        <section className="bg-gradient-to-r from-slate-950 via-indigo-950 to-blue-950 py-16 text-white">
          <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-8 px-4 sm:px-6 md:flex-row md:items-center lg:px-8">
            <div><p className="text-sm font-semibold text-indigo-300">Ready to improve your quoting process?</p><h2 className="mt-2 text-3xl font-black">Create your first professional quote today.</h2><p className="mt-3 max-w-2xl text-slate-300">Start with the free trial and see how much faster your business can quote, send, and follow up.</p></div>
            <Link href="/signup" className="shrink-0 rounded-xl bg-white px-6 py-3.5 font-bold text-slate-950 hover:bg-slate-100">Start free trial →</Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
