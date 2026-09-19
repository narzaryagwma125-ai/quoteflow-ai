"use client";

import { PricingCard } from "@/components/PricingCard";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";

const plans = [
  {
    name: "Free",
    price: "$0",
    tagline: "After your free trial ends",
    features: [
      "Up to 3 quotes/month",
      "25 customers",
      "10 AI assists/month",
      "Secure share links",
      "PDF downloads",
    ],
    cta: "Start free",
    href: "/signup",
  },
  {
    name: "Starter",
    price: "$9",
    highlight: true,
    tagline: "For growing cleaning businesses",
    features: [
      "Up to 50 quotes/month",
      "Unlimited customers",
      "50 AI assists/month",
      "Public quote links",
      "Basic branding",
      "Priority support",
    ],
    cta: "Start free trial",
    href: "/signup?plan=starter",
  },
  {
    name: "Business",
    price: "$19",
    tagline: "For busy multi-crew operations",
    features: [
      "Unlimited quotes",
      "Unlimited customers",
      "200 AI assists/month",
      "Everything in Starter",
      "Enhanced limits & support",
    ],
    cta: "Start free trial",
    href: "/signup?plan=business",
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <SiteNav />
      <main className="mx-auto max-w-6xl px-4 py-12">
        <h1 className="text-center text-3xl font-extrabold text-slate-900">Simple, transparent pricing</h1>
        <p className="mt-2 text-center text-slate-600">
          Start your 5-day free trial with 50 quotes and 50 AI assists. All prices in USD via secure Stripe checkout. Cancel anytime.
        </p>
        <div className="mt-10 grid gap-6 lg:grid-cols-3">
          {plans.map((p) => (
            <PricingCard key={p.name} {...p} onSelect={() => (window.location.href = p.href)} />
          ))}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}