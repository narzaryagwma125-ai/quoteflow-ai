"use client";

import { PricingCard } from "@/components/PricingCard";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";

const plans = [
  { name: "Free", price: "$0", tagline: "For trying QuoteFlow AI", features: ["Up to 3 quotes/month", "25 customers", "10 AI assists/month", "Secure share links", "PDF downloads"], cta: "Start free", href: "/signup" },
  { name: "Basic", price: "$6", highlight: false, tagline: "For freelancers and small businesses", features: ["200 quotes/month", "Unlimited customers", "200 AI assists/month", "Public quote links", "Basic branding"], cta: "Get Basic", href: "/signup?plan=starter" },
  { name: "Pro", price: "$12", highlight: true, tagline: "For businesses ready to scale", features: ["1,000 quotes/month", "Unlimited customers", "1,000 AI assists/month", "Advanced dashboard", "Everything in Basic"], cta: "Get Pro", href: "/signup?plan=pro" },
  { name: "Business", price: "$24", tagline: "For teams and high-volume operations", features: ["Unlimited quotes", "Unlimited AI assists", "Unlimited customers", "Advanced dashboard", "Priority support", "Business-ready workflows"], cta: "Get Business", href: "/signup?plan=business" },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <SiteNav />
      <main className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-bold uppercase tracking-wider text-brand-600">Plans that scale with you</p>
          <h1 className="mt-2 text-4xl font-black tracking-tight text-slate-950">Simple, transparent pricing</h1>
          <p className="mt-4 leading-7 text-slate-600">Start free and upgrade when your quoting volume grows. All paid plans use secure Razorpay checkout.</p>
        </div>
        <div className="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {plans.map((p) => <PricingCard key={p.name} {...p} onSelect={() => (window.location.href = p.href)} />)}
        </div>
        <div className="mx-auto mt-10 max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
          <p className="font-bold text-slate-900">International customers</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">Prices are displayed in INR. Razorpay can process eligible international card payments when international payments and the required payment methods are enabled on your Razorpay account.</p>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
