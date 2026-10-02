"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function VerifyEmailPage() {
  const [token, setToken] = useState("");
  const [status, setStatus] = useState<"loading" | "ok" | "error" | "invalid">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("token") ?? "";
    setToken(t);
    if (!t) {
      setStatus("invalid");
      setMessage("Missing verification token.");
      return;
    }
  }, []);

  useEffect(() => {
    if (!token) {
      setStatus("invalid");
      setMessage("Missing verification token.");
      return;
    }
    let cancelled = false;
    api<{ message: string }>("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) })
      .then((res) => {
        if (!cancelled) {
          setStatus("ok");
          setMessage(res.message);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setStatus("error");
          setMessage(err instanceof Error ? err.message : "Verification failed.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        {status === "loading" && <p className="text-sm text-slate-500">Verifying…</p>}
        {status === "ok" && (
          <>
            <h1 className="text-lg font-bold text-green-700">Email verified</h1>
            <p className="mt-2 text-sm text-slate-600">{message}</p>
            <Link href="/login" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
              Log in
            </Link>
          </>
        )}
        {status === "error" && (
          <>
            <h1 className="text-lg font-bold text-red-600">Couldn&apos;t verify</h1>
            <p className="mt-2 text-sm text-slate-600">{message}</p>
            <Link href="/forgot-password" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
              Get help
            </Link>
          </>
        )}
        {status === "invalid" && (
          <>
            <h1 className="text-lg font-bold text-slate-800">Invalid link</h1>
            <p className="mt-2 text-sm text-slate-600">{message}</p>
            <Link href="/" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
              Go home
            </Link>
          </>
        )}
      </div>
    </main>
  );
}