"use client";

import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button } from "@/components/Button";
import { Select } from "@/components/Select";
import { Textarea } from "@/components/Textarea";
import { api } from "@/lib/api";

type Feature = "service_description" | "rewrite" | "introduction" | "follow_up";

const FEATURES: { value: Feature; label: string }[] = [
  { value: "service_description", label: "Service description" },
  { value: "rewrite", label: "Rewrite description" },
  { value: "introduction", label: "Introduction" },
  { value: "follow_up", label: "Follow-up message" },
];

export function AIAssist({
  open,
  onClose,
  serviceName,
  currentDescription,
  businessName,
  customerName,
  quoteNumber,
  onInsertDescription,
  onInsertNotes,
}: {
  open: boolean;
  onClose: () => void;
  serviceName: string;
  currentDescription: string;
  businessName: string;
  customerName: string;
  quoteNumber: string;
  onInsertDescription: (text: string) => void;
  onInsertNotes: (text: string) => void;
}) {
  const [feature, setFeature] = useState<Feature>("service_description");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [usageRemaining, setUsageRemaining] = useState<number | null>(null);

  const generate = async () => {
    setError(null);
    setResult(null);
    const effectivePrompt = prompt.trim();
    if (feature === "rewrite") {
      if (!currentDescription.trim()) return setError("The selected item has no description to rewrite.");
    } else if (feature === "service_description") {
      if (!serviceName.trim()) return setError("Enter a service name or short description first.");
    } else if (feature === "introduction") {
      if (!businessName.trim() && !customerName.trim()) {
        return setError("Complete your business profile or add a customer first.");
      }
    }
    setLoading(true);
    try {
      let body: Record<string, string> = {};
      switch (feature) {
        case "service_description":
          body = { service_name: serviceName, notes: effectivePrompt };
          break;
        case "rewrite":
          body = { text: currentDescription, tone: effectivePrompt || "professional" };
          break;
        case "introduction":
          body = { business_name: businessName, customer_name: customerName, summary: effectivePrompt };
          break;
        case "follow_up":
          body = { customer_name: customerName, quote_number: quoteNumber, context: effectivePrompt };
          break;
      }
      const res = await api<{ text: string; usage_remaining: number }>(
        `/ai/${feature === "follow_up" ? "follow-up-message" : feature === "service_description" ? "service-description" : feature}`,
        { method: "POST", body: JSON.stringify(body) },
      );
      if (!res || typeof res.text !== "string") {
        throw new Error("The AI assistant returned an unexpected response.");
      }
      setResult(res.text);
      setUsageRemaining(res.usage_remaining);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI request failed.");
    } finally {
      setLoading(false);
    }
  };

  const insert = () => {
    if (!result) return;
    if (feature === "introduction" || feature === "follow_up") {
      onInsertNotes(result);
    } else {
      onInsertDescription(result);
    }
    resetAndClose();
  };

  const resetAndClose = () => {
    setResult(null);
    setUsageRemaining(null);
    setPrompt("");
    onClose();
  };

  return (
    <Modal open={open} title="AI assistant" onClose={resetAndClose}>
      <div className="space-y-4">
        <Select label="What do you need?" value={feature} onChange={(e) => { setFeature(e.target.value as Feature); setResult(null); }}>
          {FEATURES.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </Select>

        {feature === "service_description" && (
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            Generates a professional description for the currently selected service:{" "}
            <span className="font-medium">{serviceName || "—"}</span>
          </p>
        )}
        {feature === "rewrite" && (
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">Rewrites the selected line item&apos;s description. You can type a tone like “more concise” or “even more professional”.</p>
        )}
        {feature === "introduction" && (
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            Drafts an introduction to place in the Notes field. Customer: <span className="font-medium">{customerName || "—"}</span>.
          </p>
        )}
        {feature === "follow_up" && (
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            Drafts a polite follow-up message to send to the customer outside QuoteFlow.
          </p>
        )}

        <Textarea
          label={feature === "rewrite" ? "Tone (optional)" : "Context (optional)"}
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={
            feature === "follow_up"
              ? "e.g. They asked for pricing after the holidays; remind them the quote is still valid."
              : "Add context for a more tailored result — or leave blank."
          }
        />

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button onClick={() => void generate()} loading={loading}>
          Generate
        </Button>

        {result && (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">
              Generated by AI {usageRemaining !== null ? `· ${usageRemaining} AI uses left this month` : ""}
            </p>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="whitespace-pre-wrap text-sm text-slate-800">{result}</p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setResult(null)}>
                Regenerate
              </Button>
              <Button size="sm" onClick={insert}>
                Use this
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}