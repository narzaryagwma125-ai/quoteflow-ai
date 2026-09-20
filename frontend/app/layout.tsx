import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "QuoteFlow AI — AI-powered quotes for growing businesses",
    template: "%s · QuoteFlow AI",
  },
  description:
    "QuoteFlow AI helps service businesses create professional quotes, manage customers, send secure quote links, and use AI to win more work.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#4f46e5",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}