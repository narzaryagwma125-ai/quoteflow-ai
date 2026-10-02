"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { Input } from "@/components/Input";
import { Textarea } from "@/components/Textarea";
import { api, asList } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Customer, Quote } from "@/types";

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", address: "", notes: "" });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const c = await api<Customer>(`/customers/${id}`);
      setCustomer(c);
      setForm({
        name: c.name,
        email: c.email || "",
        phone: c.phone || "",
        address: c.address || "",
        notes: c.notes || "",
      });
      setQuotes(asList<Quote>(await api<unknown>(`/quotes?customer_id=${id}&page_size=50`)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customer.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api<Customer>(`/customers/${id}`, { method: "PUT", body: JSON.stringify(form) });
      setCustomer(updated);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save customer.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    await api(`/customers/${id}`, { method: "DELETE" });
    router.push("/customers");
  };

  if (loading) {
    return (
      <RequireAuth><DashboardShell><Loading /></DashboardShell></RequireAuth>
    );
  }

  return (
    <RequireAuth>
      <DashboardShell>
        {error && <ErrorState message={error} onRetry={() => void load()} />}
        {customer && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">{customer.name}</h1>
                <p className="text-sm text-slate-500">
                  Added {formatDate(customer.created_at)} · {quotes.length} quote(s)
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setEditing((v) => !v)}>
                  {editing ? "View" : "Edit"}
                </Button>
                <Button variant="danger" onClick={() => setConfirmOpen(true)}>
                  Delete
                </Button>
              </div>
            </div>

            {editing ? (
              <Card title="Edit customer">
                <form onSubmit={save} className="grid max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
                  <Input label="Name" required value={form.name} onChange={set("name")} className="sm:col-span-2" />
                  <Input label="Email" type="email" value={form.email} onChange={set("email")} className="sm:col-span-2" />
                  <Input label="Phone" value={form.phone} onChange={set("phone")} className="sm:col-span-2" />
                  <Textarea label="Address" rows={3} value={form.address} onChange={set("address")} className="sm:col-span-2" />
                  <Textarea label="Notes" rows={3} value={form.notes} onChange={set("notes")} className="sm:col-span-2" />
                  <div className="flex justify-end gap-3 sm:col-span-2">
                    <Button variant="secondary" type="button" onClick={() => setEditing(false)}>Cancel</Button>
                    <Button type="submit" loading={saving}>Save</Button>
                  </div>
                </form>
              </Card>
            ) : (
              <Card title="Details">
                <dl className="grid gap-3 text-sm sm:grid-cols-2">
                  <Line k="Email" v={customer.email || "—"} />
                  <Line k="Phone" v={customer.phone || "—"} />
                  <div className="sm:col-span-2"><Line k="Address" v={customer.address || "—"} /></div>
                  <div className="sm:col-span-2"><Line k="Notes" v={customer.notes || "—"} /></div>
                </dl>
              </Card>
            )}

            <Card title="Quotes">
              {quotes.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No quotes yet.{" "}
                  <span
                    className="cursor-pointer text-brand-600 hover:underline"
                    onClick={() => router.push(`/quotes/new?customer_id=${id}`)}
                  >
                    Create one
                  </span>
                </p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {quotes.map((q) => (
                    <li
                      key={q.id}
                      className="flex cursor-pointer items-center justify-between py-3 hover:bg-slate-50"
                      onClick={() => router.push(`/quotes/${q.id}`)}
                    >
                      <span className="font-medium text-slate-800">{q.quote_number}</span>
                      <span className="text-sm text-slate-500">{formatDate(q.issue_date)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <ConfirmDialog
              open={confirmOpen}
              title="Delete customer"
              message={`Permanently delete ${customer.name}? This cannot be undone.`}
              confirmLabel="Delete"
              danger
              onConfirm={remove}
              onCancel={() => setConfirmOpen(false)}
            />
          </div>
        )}
      </DashboardShell>
    </RequireAuth>
  );
}

function Line({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-100 py-2">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-800">{v}</dd>
    </div>
  );
}