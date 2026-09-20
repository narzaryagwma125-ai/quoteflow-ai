"use client";

import { useCallback, useEffect, useState } from "react";
import { DashboardShell } from "@/components/DashboardShell";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { api } from "@/lib/api";
import type { BusinessProfile, TemplateSettings } from "@/types";

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const size = bytes / Math.pow(1024, i);
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

const PLACEHOLDER_GROUPS: { title: string; items: string[] }[] = [
  {
    title: "Business",
    items: [
      "business_name",
      "business_owner",
      "business_email",
      "business_phone",
      "business_address",
      "business_tax_id",
      "business_currency",
    ],
  },
  {
    title: "Quote",
    items: ["quote_number", "issue_date", "valid_until", "status", "currency"],
  },
  {
    title: "Customer",
    items: ["customer_name", "customer_company", "customer_email", "customer_phone", "customer_address"],
  },
  {
    title: "Totals",
    items: ["subtotal", "discount", "tax_rate", "tax_amount", "total"],
  },
  {
    title: "Other",
    items: ["notes", "payment_terms", "signature", "line_items"],
  },
];

export default function BusinessPage() {
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [logoSaving, setLogoSaving] = useState(false);
  const [logoPosition, setLogoPosition] = useState<"left" | "center" | "right">("left");
  const [logoSize, setLogoSize] = useState<"small" | "medium" | "large">("medium");
  const [showLogo, setShowLogo] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"view" | "edit">("view");

  const [template, setTemplate] = useState<TemplateSettings | null>(null);
  const [templateLoading, setTemplateLoading] = useState(true);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [templateUploading, setTemplateUploading] = useState(false);
  const [templateTesting, setTemplateTesting] = useState(false);
  const [selectedType, setSelectedType] = useState<"default" | "custom_docx">("default");

  const fields = useCallback((p: BusinessProfile | null) =>
    p
      ? {
          business_name: p.business_name,
          owner_name: p.owner_name,
          email: p.email,
          phone: p.phone || "",
          address_line_1: p.address_line_1 || "",
          address_line_2: p.address_line_2 || "",
          city: p.city || "",
          state_or_province: p.state_or_province || "",
          postal_code: p.postal_code || "",
          country: p.country,
          currency: p.currency,
          timezone: p.timezone,
          tax_rate: p.tax_rate_percent,
        }
      : {
          business_name: "",
          owner_name: "",
          email: "",
          phone: "",
          address_line_1: "",
          address_line_2: "",
          city: "",
          state_or_province: "",
          postal_code: "",
          country: "US",
          currency: "INR",
          timezone: "America/New_York",
          tax_rate: "0",
        }, []);

  const [form, setForm] = useState(() => fields(null));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = await api<BusinessProfile>("/business-profile");
      setProfile(p);
      setForm(fields(p));
      setLogoPosition(p.logo_position);
      setLogoSize(p.logo_size);
      setShowLogo(p.show_logo_on_quotation);
    } catch (err) {
      const status = (err as { status?: number }).status;
      if (status === 404) {
        setProfile(null);
        setMode("edit");
      } else {
        setError(err instanceof Error ? err.message : "Failed to load profile.");
      }
    } finally {
      setLoading(false);
    }
  }, [fields]);

  const loadTemplate = useCallback(async () => {
    setTemplateLoading(true);
    try {
      const ts = await api<TemplateSettings>("/business-profile/template");
      setTemplate(ts);
      setSelectedType(ts.template_type);
    } catch {
      // Profile may not exist yet; template state stays null.
    } finally {
      setTemplateLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void loadTemplate();
  }, [load, loadTemplate]);

  const set = (key: string, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const body = { ...form };
      if (Number.isNaN(parseFloat(body.tax_rate))) {
        throw new Error("Enter a valid tax rate. Use 0 for none.");
      }
      const saved = await api<BusinessProfile>("/business-profile", { method: "PUT", body: JSON.stringify(body) });
      setProfile(saved);
      setForm(fields(saved));
      setMode("view");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile.");
    } finally {
      setSaving(false);
    }
  };

  const uploadLogo = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/business-profile/logo", { method: "POST", body: fd, credentials: "same-origin" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Logo upload failed." }));
        throw new Error(typeof body.detail === "string" ? body.detail : "Logo upload failed.");
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logo upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const removeLogo = async () => {
    setLogoSaving(true);
    setError(null);
    try {
      const saved = await api<BusinessProfile>("/business-profile/logo", { method: "DELETE" });
      setProfile(saved);
      setForm(fields(saved));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete logo.");
    } finally {
      setLogoSaving(false);
    }
  };

  const saveLogoSettings = async () => {
    setLogoSaving(true);
    setError(null);
    try {
      const saved = await api<BusinessProfile>("/business-profile", {
        method: "PUT",
        body: JSON.stringify({
          logo_position: logoPosition,
          logo_size: logoSize,
          show_logo_on_quotation: showLogo,
        }),
      });
      setProfile(saved);
      setLogoPosition(saved.logo_position);
      setLogoSize(saved.logo_size);
      setShowLogo(saved.show_logo_on_quotation);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save logo settings.");
    } finally {
      setLogoSaving(false);
    }
  };

  // ── Custom DOCX template actions ─────────────────────────────────
  const uploadTemplate = async (file: File | undefined) => {
    if (!file) return;
    setTemplateUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/business-profile/template", { method: "POST", body: fd, credentials: "same-origin" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Template upload failed." }));
        throw new Error(typeof body.detail === "string" ? body.detail : "Template upload failed.");
      }
      const ts: TemplateSettings = await res.json();
      setTemplate(ts);
      setSelectedType("custom_docx");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Template upload failed.");
    } finally {
      setTemplateUploading(false);
    }
  };

  const downloadSampleTemplate = () => {
    window.open("/api/business-profile/template/sample", "_blank");
  };

  const previewTemplate = () => {
    if (!template?.has_custom_template) return;
    window.open("/api/business-profile/template/preview", "_blank");
  };

  const testTemplate = async () => {
    if (!template?.has_custom_template) return;
    setTemplateTesting(true);
    setError(null);
    try {
      const res = await fetch("/api/business-profile/template/test", { method: "POST", credentials: "same-origin" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Could not render PDF preview." }));
        throw new Error(typeof body.detail === "string" ? body.detail : "Could not render PDF preview.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Template test failed.");
    } finally {
      setTemplateTesting(false);
    }
  };

  const removeTemplate = async () => {
    setTemplateSaving(true);
    setError(null);
    try {
      const ts = await api<TemplateSettings>("/business-profile/template", { method: "DELETE" });
      setTemplate(ts);
      setSelectedType("default");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete template.");
    } finally {
      setTemplateSaving(false);
    }
  };

  const saveTemplateSettings = async () => {
    setTemplateSaving(true);
    setError(null);
    try {
      if (selectedType === "default") {
        const ts = await api<TemplateSettings>("/business-profile/template/default", { method: "POST" });
        setTemplate(ts);
      } else {
        if (!template?.has_custom_template) {
          throw new Error("Upload a custom DOCX template first.");
        }
        const ts = await api<TemplateSettings>("/business-profile/template/custom-docx", { method: "POST" });
        setTemplate(ts);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save template settings.");
    } finally {
      setTemplateSaving(false);
    }
  };

  if (loading) {
    return (
      <RequireAuth>
        <DashboardShell><Loading /></DashboardShell>
      </RequireAuth>
    );
  }

  return (
    <RequireAuth>
      <DashboardShell>
        <h1 className="mb-6 text-2xl font-bold text-slate-900">Business profile</h1>
        {error && <ErrorState message={error} />}

        {/* ── Business Logo ─────────────────────────────────────────── */}
        <Card title="Business Logo" className="mb-6">
          <p className="mb-4 text-sm text-slate-500">
            Upload a business logo (PNG, JPEG, or SVG, up to 2 MB). It is shown in the header of generated
            quotations. If no logo is uploaded, only the business name appears.
          </p>

          <div className="flex flex-wrap items-start gap-4">
            <div className="flex h-20 w-20 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 p-1">
              {profile?.has_logo ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img alt="Business logo" src="/api/business-profile/logo" className="max-h-full max-w-full object-contain" />
              ) : (
                <span className="text-xs text-slate-400">No logo</span>
              )}
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-3">
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/svg+xml,.png,.jpg,.jpeg,.svg"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void uploadLogo(file);
                    e.target.value = "";
                  }}
                  className="text-sm text-slate-600 file:mr-3 file:rounded-lg file:border file:border-slate-300 file:bg-white file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-50"
                  disabled={!profile || uploading || logoSaving}
                />
                {uploading && <span className="text-sm text-slate-500">Uploading…</span>}
                {profile?.has_logo && (
                  <button
                    type="button"
                    onClick={() => void removeLogo()}
                    className="inline-flex items-center gap-1.5 rounded-md border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-600 shadow-sm hover:bg-red-50 transition-colors"
                    disabled={logoSaving}
                  >
                    Remove
                  </button>
                )}
                {!profile && <span className="text-sm text-slate-400 italic">Create your business profile first.</span>}
              </div>

              <div className="mt-4 grid max-w-lg grid-cols-1 gap-4 sm:grid-cols-3">
                <Select label="Logo position" value={logoPosition} onChange={(e) => setLogoPosition(e.target.value as "left" | "center" | "right")}>
                  <option value="left">Left</option>
                  <option value="center">Center</option>
                  <option value="right">Right</option>
                </Select>
                <Select label="Logo size" value={logoSize} onChange={(e) => setLogoSize(e.target.value as "small" | "medium" | "large")}>
                  <option value="small">Small</option>
                  <option value="medium">Medium</option>
                  <option value="large">Large</option>
                </Select>
                <label className="flex items-center gap-2 self-end pb-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={showLogo}
                    onChange={(e) => setShowLogo(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  Show logo on quotation
                </label>
              </div>

              <div className="mt-4">
                <Button size="sm" onClick={() => void saveLogoSettings()} loading={logoSaving} disabled={!profile}>
                  Save logo settings
                </Button>
              </div>
            </div>
          </div>
        </Card>

        <Card title={mode === "edit" ? (profile ? "Edit profile" : "Create profile") : "Details"}>
          {mode === "view" && profile ? (
            <div className="max-w-xl space-y-1 text-sm">
              <Row k="Business name" v={profile.business_name} />
              <Row k="Owner" v={profile.owner_name} />
              <Row k="Email" v={profile.email} />
              <Row k="Phone" v={profile.phone || "—"} />
              <Row k="Address" v={[profile.address_line_1, profile.address_line_2, profile.city, profile.state_or_province, profile.postal_code].filter(Boolean).join(", ") || "—"} />
              <Row k="Country" v={profile.country} />
              <Row k="Currency" v={profile.currency} />
              <Row k="Tax rate" v={`${profile.tax_rate_percent}%${profile.tax_rate_unconfigured ? " (not configured)" : ""}`} />
              <div className="pt-3">
                <Button variant="secondary" size="sm" onClick={() => setMode("edit")}>
                  Edit
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={save} className="grid max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
              <Input label="Business name" required value={form.business_name} onChange={(e) => set("business_name", e.target.value)} />
              <Input label="Owner name" required value={form.owner_name} onChange={(e) => set("owner_name", e.target.value)} />
              <Input label="Contact email" type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} />
              <Input label="Phone (optional)" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
              <Input label="Address line 1" value={form.address_line_1} onChange={(e) => set("address_line_1", e.target.value)} />
              <Input label="Address line 2" value={form.address_line_2} onChange={(e) => set("address_line_2", e.target.value)} />
              <Input label="City" value={form.city} onChange={(e) => set("city", e.target.value)} />
              <Input label="State / Province" value={form.state_or_province} onChange={(e) => set("state_or_province", e.target.value)} />
              <Input label="Postal code" value={form.postal_code} onChange={(e) => set("postal_code", e.target.value)} />
              <Select label="Country" value={form.country} onChange={(e) => set("country", e.target.value)}>
                <option value="US">United States</option>
                <option value="CA">Canada</option>
              </Select>
              <Select label="Currency" value={form.currency} onChange={(e) => set("currency", e.target.value)}>
                <option value="INR">INR (₹)</option>
                <option value="USD">USD ($)</option>
                <option value="CAD">CAD (CA$)</option>
                <option value="GBP">GBP (£)</option>
                <option value="AUD">AUD (A$)</option>
              </Select>
              <Input label="Tax rate (%) — 0 for none" inputMode="decimal" value={form.tax_rate} onChange={(e) => set("tax_rate", e.target.value)} hint="e.g. 7.5 for 7.5%" />
              <Input label="Timezone" value={form.timezone} onChange={(e) => set("timezone", e.target.value)} className="sm:col-span-2" />
              <div className="flex justify-end gap-3 sm:col-span-2">
                {profile && <Button variant="secondary" type="button" onClick={() => { setMode("view"); setForm(fields(profile)); }}>Cancel</Button>}
                <Button type="submit" loading={saving}>Save</Button>
              </div>
            </form>
          )}
        </Card>

        {/* ── Custom DOCX Template ─────────────────────────────────── */}
        <div className="mt-6">
          <Card title="Custom DOCX Template">
            <p className="mb-4 text-sm text-slate-500">
              Upload a DOCX file containing QuoteFlow placeholders. If no custom DOCX template is selected,
              QuoteFlow will use the default quotation design.
            </p>

            {templateLoading ? (
              <Loading />
            ) : (
              <div className="space-y-4">
                {/* ── Template type selection ───────────────────────── */}
                <div className="space-y-3">
                  <label className="flex items-start gap-3 cursor-pointer group">
                    <input
                      type="radio"
                      name="template_type"
                      className="mt-0.5 h-4 w-4 text-blue-600 border-slate-300 focus:ring-blue-500"
                      checked={selectedType === "default"}
                      onChange={() => setSelectedType("default")}
                    />
                    <div>
                      <span className="text-sm font-medium text-slate-900 group-hover:text-blue-600 transition-colors">
                        QuoteFlow Default Template
                      </span>
                      <p className="text-xs text-slate-500 mt-0.5">Use the built-in professional quotation layout</p>
                    </div>
                  </label>

                  <label className="flex items-start gap-3 cursor-pointer group">
                    <input
                      type="radio"
                      name="template_type"
                      className="mt-0.5 h-4 w-4 text-blue-600 border-slate-300 focus:ring-blue-500"
                      checked={selectedType === "custom_docx"}
                      onChange={() => setSelectedType("custom_docx")}
                    />
                    <div>
                      <span className="text-sm font-medium text-slate-900 group-hover:text-blue-600 transition-colors">
                        Use Custom DOCX Template
                      </span>
                      <p className="text-xs text-slate-500 mt-0.5">Fill your own .docx with QuoteFlow data (max 5 MB)</p>
                    </div>
                  </label>
                </div>

                {/* ── Upload + sample buttons ──────────────────────── */}
                <div className="pl-7 border-l-2 border-slate-100 space-y-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <input
                      type="file"
                      accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void uploadTemplate(file);
                        e.target.value = "";
                      }}
                      className="text-sm text-slate-600 file:mr-3 file:rounded-lg file:border file:border-slate-300 file:bg-white file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-50"
                      disabled={templateSaving || templateUploading}
                    />
                    {templateUploading && <span className="text-sm text-slate-500">Uploading…</span>}
                    <button
                      type="button"
                      onClick={downloadSampleTemplate}
                      className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
                      Download sample DOCX
                    </button>
                  </div>

                  {/* ── Current template info ──────────────────────── */}
                  {template?.has_custom_template && (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-slate-900 truncate">
                            {template.custom_docx_filename}
                          </p>
                          <p className="text-xs text-slate-500">
                            {formatFileSize(template.custom_docx_size)} · Uploaded {formatDate(template.custom_docx_uploaded_at)} · v{template.custom_docx_version}
                          </p>
                        </div>
                        <div className="flex shrink-0 gap-2 ml-3">
                          <button
                            type="button"
                            onClick={() => void previewTemplate()}
                            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
                            disabled={templateSaving}
                          >
                            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>
                            View DOCX
                          </button>
                          <button
                            type="button"
                            onClick={() => void testTemplate()}
                            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
                            disabled={templateSaving || templateTesting}
                          >
                            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-9-9m9 9a9 9 0 01-9 9m9-9H12m9 0a9 9 0 00-3-6.7M12 3v9" /></svg>
                            {templateTesting ? "Testing…" : "Test PDF"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void removeTemplate()}
                            className="inline-flex items-center gap-1.5 rounded-md border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-600 shadow-sm hover:bg-red-50 transition-colors"
                            disabled={templateSaving}
                          >
                            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
                            Remove
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* ── Save settings ──────────────────────────────── */}
                  <div className="flex items-center gap-3">
                    <Button size="sm" onClick={() => void saveTemplateSettings()} loading={templateSaving}>
                      Save settings
                    </Button>
                    {selectedType !== (template?.template_type ?? "default") && (
                      <span className="text-xs text-slate-400 italic">You have unsaved template settings.</span>
                    )}
                  </div>

                  {template && !template.has_custom_template && template.template_type === "custom_docx" && (
                    <p className="text-sm text-amber-600">
                      Custom DOCX file is missing. Please re-upload.
                    </p>
                  )}

                  {(!template || !template.has_custom_template) && template?.template_type !== "custom_docx" && (
                    <p className="text-xs text-slate-400 italic">
                      No custom DOCX template uploaded. The default QuoteFlow template will be used for all quotation PDFs.
                    </p>
                  )}
                </div>

                {/* ── Placeholder help ─────────────────────────────── */}
                <div className="rounded-lg border border-slate-200 p-4">
                  <p className="mb-3 text-sm font-semibold text-slate-900">Supported placeholders</p>
                  <p className="mb-3 text-xs text-slate-500">
                    Add these tokens anywhere in your DOCX (body, table cells, headers, or footers).
                    Use <code className="rounded bg-slate-100 px-1 py-0.5 text-[11px]">{"{{line_items}}"}</code> to insert
                    the item table with columns #, Description, Quantity, Unit, Unit Price, and Amount.
                  </p>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {PLACEHOLDER_GROUPS.map((group) => (
                      <div key={group.title}>
                        <p className="text-xs font-semibold text-blue-700">{group.title}</p>
                        <ul className="mt-1 space-y-1">
                          {group.items.map((item) => (
                            <li key={item}>
                              <code className="rounded bg-slate-100 px-1 py-0.5 text-[11px] text-slate-700">{"{{" + item + "}}"}</code>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </Card>
        </div>
      </DashboardShell>
    </RequireAuth>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-100 py-2">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-800">{v}</dd>
    </div>
  );
}