"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { api } from "@/lib/api";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (token.length < 16) {
      setError("This reset link looks invalid. Request a new one.");
      return;
    }
    if (password.length < 10) {
      setError("Password must be at least 10 characters.");
      return;
    }
    setLoading(true);
    try {
      await api<{ message: string }>("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        {done ? (
          <>
            <h1 className="text-lg font-bold text-slate-900">Password updated</h1>
            <p className="mt-2 text-sm text-slate-600">You can now log in with your new password.</p>
            <Link href="/login" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
              Log in
            </Link>
          </>
        ) : (
          <>
            <h1 className="text-center text-2xl font-bold text-slate-900">Choose a new password</h1>
            <form onSubmit={submit} className="mt-6 space-y-4">
              <Input
                label="New password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                hint="At least 10 characters."
              />
              {error && <p className="text-sm text-red-600">{error}</p>}
              <Button type="submit" loading={loading} className="w-full">
                Set new password
              </Button>
            </form>
          </>
        )}
      </div>
    </main>
  );
}