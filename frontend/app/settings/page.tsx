"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { api } from "@/lib/api";
import type { Me } from "@/types";

export default function SettingsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        setMe(await api<Me>("/me"));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load account.");
      }
    };
    void load();
  }, []);

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    if (password.length < 10) {
      setError("New password must be at least 10 characters.");
      return;
    }
    setBusy(true);
    try {
      await api<{ message: string }>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ new_password: password }),
      });
      setPassword("");
      setMessage("Password updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update password.");
    } finally {
      setBusy(false);
    }
  };

  const resendVerification = async () => {
    setError(null);
    setMessage(null);
    try {
      const res = await api<{ message: string }>("/auth/resend-verification", { method: "POST" });
      setMessage(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resend.");
    }
  };

  return (
    <RequireAuth>
      <DashboardShell>
        <h1 className="mb-6 text-2xl font-bold text-slate-900">Settings</h1>
        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        {message && <div className="mb-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">{message}</div>}

        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Account">
            {me && (
              <div className="space-y-2 text-sm">
                <p>
                  <span className="text-slate-500">Email: </span>
                  <span className="font-medium">{me.email}</span>
                </p>
                <p>
                  <span className="text-slate-500">Verification: </span>
                  {me.is_email_verified ? (
                    <span className="text-green-600">Verified</span>
                  ) : (
                    <>
                      <span className="text-amber-600">Pending</span>{" "}
                      <button onClick={() => void resendVerification()} className="text-brand-600 hover:underline">
                        Resend verification email
                      </button>
                    </>
                  )}
                </p>
                <p>
                  <span className="text-slate-500">Plan: </span>
                  <span className="font-medium capitalize">{me.plan}</span>
                </p>
              </div>
            )}
            <div className="mt-6 border-t border-slate-100 pt-4">
              <Button variant="danger" size="sm" onClick={() => setConfirmDelete(true)}>
                Delete my account
              </Button>
            </div>
          </Card>

          <Card title="Change password">
            <form onSubmit={changePassword} className="space-y-4">
              <Input
                label="New password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                hint="At least 10 characters."
              />
              <Button type="submit" loading={busy}>
                Update password
              </Button>
            </form>
          </Card>
        </div>

        <ConfirmDialog
          open={confirmDelete}
          title="Delete account"
          message="This permanently deletes your account, customers, quotes, and billing data. This cannot be undone."
          confirmLabel="Delete everything"
          danger
          loading={busy}
          onConfirm={async () => {
            await api("/auth/delete-account", { method: "POST" });
            window.location.href = "/";
          }}
          onCancel={() => setConfirmDelete(false)}
        />
      </DashboardShell>
    </RequireAuth>
  );
}