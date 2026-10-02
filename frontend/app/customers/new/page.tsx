"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { Textarea } from "@/components/Textarea";
import { api } from "@/lib/api";
import type { Customer } from "@/types";

export default function NewCustomerPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", phone: "", address: "", notes: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("Name is required.");
      return;
    }
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      setError("Enter a valid email address.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const customer = await api<Customer>("/customers", { method: "POST", body: JSON.stringify(form) });
      router.push(`/customers/${customer.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create customer.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <RequireAuth>
      <DashboardShell>
        <h1 className="mb-6 text-2xl font-bold text-slate-900">New customer</h1>
        <Card>
          <form onSubmit={submit} className="grid max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
            <Input label="Name" required value={form.name} onChange={set("name")} className="sm:col-span-2" />
            <Input label="Email" type="email" value={form.email} onChange={set("email")} className="sm:col-span-2" />
            <Input label="Phone" value={form.phone} onChange={set("phone")} className="sm:col-span-2" />
            <Textarea label="Address" rows={3} value={form.address} onChange={set("address")} className="sm:col-span-2" />
            <Textarea label="Notes" rows={3} value={form.notes} onChange={set("notes")} className="sm:col-span-2" />
            {error && <p className="text-sm text-red-600 sm:col-span-2">{error}</p>}
            <div className="flex justify-end gap-3 sm:col-span-2">
              <Button variant="secondary" type="button" onClick={() => router.back()}>Cancel</Button>
              <Button type="submit" loading={saving}>Save customer</Button>
            </div>
          </form>
        </Card>
      </DashboardShell>
    </RequireAuth>
  );
}