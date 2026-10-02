"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Enter a valid email address.");
      return;
    }
    setLoading(true);
    try {
      await api<{ message: string }>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        {sent ? (
          <>
            <h1 className="text-lg font-bold text-slate-900">Check your email</h1>
            <p className="mt-2 text-sm text-slate-600">
              If an account exists for <span className="font-medium">{email}</span>, a password
              reset link is on its way.
            </p>
            <Link href="/login" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
              Back to log in
            </Link>
          </>
        ) : (
          <>
            <h1 className="text-center text-2xl font-bold text-slate-900">Reset your password</h1>
            <p className="mt-1 text-center text-sm text-slate-500">
              Enter your email and we&apos;ll send you a reset link.
            </p>
            <form onSubmit={submit} className="mt-6 space-y-4">
              <Input
                label="Email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              {error && <p className="text-sm text-red-600">{error}</p>}
              <Button type="submit" loading={loading} className="w-full">
                Send reset link
              </Button>
            </form>
            <p className="mt-4 text-center text-sm text-slate-500">
              Remembered it?{" "}
              <Link href="/login" className="text-brand-600 hover:underline">
                Log in
              </Link>
            </p>
          </>
        )}
      </div>
    </main>
  );
}