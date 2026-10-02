"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

declare global {
  interface Window {
    paypal?: {
      Buttons: (options: {
        createOrder: () => Promise<string>;
        onApprove: (data: { orderID: string }) => Promise<void>;
        onCancel?: () => void;
        onError?: (error: unknown) => void;
      }) => {
        render: (container: HTMLElement) => Promise<void>;
      };
    };
  }
}

type Props = {
  plan: "starter" | "pro" | "business";
  disabled?: boolean;
};

type CheckoutResponse = {
  provider: "paypal";
  order_id: string;
  paypal_client_id: string;
  currency: "USD";
  amount: string;
};

let paypalSdkPromise: Promise<void> | null = null;

function loadPayPalSdk(clientId: string): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("Browser required."));
  if (window.paypal) return Promise.resolve();
  if (paypalSdkPromise) return paypalSdkPromise;

  paypalSdkPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      'script[data-quoteflow-paypal="true"]'
    );
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("Unable to load PayPal.")));
      return;
    }

    const script = document.createElement("script");
    script.src =
      `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}` +
      "&currency=USD&intent=capture";
    script.async = true;
    script.dataset.quoteflowPaypal = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Unable to load PayPal Checkout."));
    document.head.appendChild(script);
  });

  return paypalSdkPromise;
}

export function PayPalCheckoutButton({ plan, disabled = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function setup() {
      if (!containerRef.current || disabled) return;
      setError(null);
      setLoading(true);

      try {
        const checkout = await api<CheckoutResponse>("/billing/checkout", {
          method: "POST",
          body: JSON.stringify({ plan, provider: "paypal" }),
        });

        await loadPayPalSdk(checkout.paypal_client_id);
        if (cancelled || !window.paypal || !containerRef.current) return;

        containerRef.current.innerHTML = "";

        await window.paypal
          .Buttons({
            createOrder: async () => checkout.order_id,
            onApprove: async ({ orderID }) => {
              await api("/billing/paypal/capture", {
                method: "POST",
                body: JSON.stringify({ order_id: orderID }),
              });
              window.location.href = "/billing?checkout=success";
            },
            onCancel: () => setError("PayPal checkout was cancelled."),
            onError: () => setError("PayPal checkout failed. Please try again."),
          })
          .render(containerRef.current);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to start PayPal checkout.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void setup();

    return () => {
      cancelled = true;
      if (containerRef.current) containerRef.current.innerHTML = "";
    };
  }, [plan, disabled]);

  return (
    <div className="mt-2">
      <div ref={containerRef} className={loading ? "min-h-10 opacity-60" : ""} />
      {loading && <p className="mt-1 text-xs text-slate-500">Loading PayPal…</p>}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
