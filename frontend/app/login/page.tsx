"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [plan, setPlan] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    setPlan(search.get("plan") ?? "");
    setSubmitted(Boolean(search.get("signup")));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Enter a valid email address.");
      return;
    }
    if (!password) {
      setError("Enter your password.");
      return;
    }
    setLoading(true);
    try {
      await api<{ message: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-center text-2xl font-bold text-slate-900">Welcome back</h1>
        <p className="mt-1 text-center text-sm text-slate-500">
          {plan ? `You selected the ${plan} plan. Log in to continue.` : "Log in to manage your quotes."}
        </p>
        {submitted && (
          <p className="mt-3 rounded-lg bg-green-50 p-3 text-sm text-green-700">
            Account created. Check your email to verify your address.
          </p>
        )}
        <form onSubmit={submit} className="mt-6 space-y-4">
          <Input
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" loading={loading} className="w-full">
            Log in
          </Button>
        </form>
        <div className="mt-4 flex items-center justify-between text-sm">
          <Link href="/forgot-password" className="text-brand-600 hover:underline">
            Forgot password?
          </Link>
          <Link href={`/signup${plan ? `?plan=${plan}` : ""}`} className="text-brand-600 hover:underline">
            Create account
          </Link>
        </div>
      </div>
    </main>
  );
}