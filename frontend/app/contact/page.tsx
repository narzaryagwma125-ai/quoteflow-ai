"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";
import { Textarea } from "@/components/Textarea";
import { api } from "@/lib/api";
import { contactSchema } from "@/lib/validation";

const subjects = [
  "Getting started",
  "Quotes & PDFs",
  "Subscription & billing",
  "Account & email verification",
  "Feature request",
  "Something else",
];

type FieldErrors = Partial<Record<"name" | "email" | "subject" | "message", string>>;

const initialValues = {
  name: "",
  email: "",
  subject: "",
  message: "",
  website: "",
};

export default function ContactPage() {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const setField = <K extends keyof typeof initialValues>(key: K, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    if (key === "name" || key === "email" || key === "subject" || key === "message") {
      setErrors((prev) => ({ ...prev, [key]: undefined }));
    }
  };

  const resetForm = () => {
    setValues(initialValues);
    setErrors({});
    setFormError(null);
    setSubmitted(false);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const parsed = contactSchema.safeParse(values);
    if (!parsed.success) {
      const flattened = parsed.error.flatten().fieldErrors;
      setErrors({
        name: flattened.name?.[0],
        email: flattened.email?.[0],
        subject: flattened.subject?.[0],
        message: flattened.message?.[0],
      });
      return;
    }

    setSubmitting(true);
    try {
      await api<{ message: string }>("/contact", {
        method: "POST",
        body: JSON.stringify(parsed.data),
      });
      setSubmitted(true);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not send your message.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <SiteNav />
      <main className="mx-auto max-w-6xl px-4 py-12">
        <h1 className="text-3xl font-extrabold text-slate-900">Contact Us</h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          Questions, feedback, or need a hand? Send us a message and our support team will get back
          to you within 1-2 business days.
        </p>

        <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_320px]">
          <div className="max-w-xl">
            {submitted ? (
              <div
                role="status"
                className="rounded-xl border border-green-200 bg-green-50 p-8 text-center"
              >
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
                  <svg
                    aria-hidden
                    className="h-6 w-6 text-green-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h2 className="mt-4 text-lg font-bold text-slate-900">Message sent</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Thank you for reaching out. We&apos;ve received your message and will reply to{" "}
                  <span className="font-medium text-slate-900">{values.email}</span> within 1-2
                  business days.
                </p>
                <Button variant="secondary" size="sm" className="mt-6" onClick={resetForm}>
                  Send another message
                </Button>
              </div>
            ) : (
              <form onSubmit={submit} noValidate className="space-y-4">
                <Input
                  label="Name"
                  autoComplete="name"
                  value={values.name}
                  error={errors.name}
                  onChange={(e) => setField("name", e.target.value)}
                />
                <Input
                  label="Email"
                  type="email"
                  autoComplete="email"
                  value={values.email}
                  error={errors.email}
                  onChange={(e) => setField("email", e.target.value)}
                />
                <Select
                  label="Subject"
                  value={values.subject}
                  error={errors.subject}
                  onChange={(e) => setField("subject", e.target.value)}
                >
                  <option value="" disabled>
                    Select a subject
                  </option>
                  {subjects.map((subject) => (
                    <option key={subject} value={subject}>
                      {subject}
                    </option>
                  ))}
                </Select>
                <Textarea
                  label="Message"
                  rows={6}
                  value={values.message}
                  error={errors.message}
                  hint="Provide as much detail as you can — it helps us help you faster."
                  onChange={(e) => setField("message", e.target.value)}
                />
                {/* Honeypot: hidden from real users; bots fill it and are silently dropped. */}
                <label className="absolute left-[-9999px] top-auto" aria-hidden>
                  <span>Leave this field empty</span>
                  <input
                    type="text"
                    tabIndex={-1}
                    autoComplete="off"
                    value={values.website}
                    onChange={(e) => setField("website", e.target.value)}
                  />
                </label>

                {formError && (
                  <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {formError}
                  </p>
                )}

                <Button type="submit" loading={submitting} className="w-full sm:w-auto">
                  Send message
                </Button>
              </form>
            )}
          </div>

          <aside className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-6">
              <h2 className="text-sm font-semibold text-slate-900">Reach us directly</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                Prefer email? Write to our support address and include as much detail as possible.
              </p>
              <p className="mt-3 text-sm">
                <a href="mailto:support@quoteflow.example" className="font-medium text-brand-600 hover:underline">
                  support@quoteflow.example
                </a>
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-6">
              <h2 className="text-sm font-semibold text-slate-900">Quick answers</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-600">
                <li>
                  <Link href="/help#getting-started" className="text-brand-600 hover:underline">
                    Getting started
                  </Link>
                </li>
                <li>
                  <Link href="/help#subscription-and-billing" className="text-brand-600 hover:underline">
                    Subscription &amp; billing
                  </Link>
                </li>
                <li>
                  <Link href="/help#faq" className="text-brand-600 hover:underline">
                    Frequently asked questions
                  </Link>
                </li>
              </ul>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-6">
              <h2 className="text-sm font-semibold text-slate-900">Response times</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                We reply to every message within 1-2 business days, Monday through Friday.
              </p>
            </div>
          </aside>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}