import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://www.quoteflowai.in"),
  title: {
    default: "AI Quote Generator for Small Businesses | QuoteFlow AI",
    template: "%s | QuoteFlow AI",
  },
  description:
    "Create professional business quotes with AI. QuoteFlow AI helps small businesses generate quotations, manage customers, send secure quote links, and create professional PDFs.",
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: "AI Quote Generator for Small Businesses | QuoteFlow AI",
    description:
      "Create professional business quotes with AI. Generate quotations, manage customers, send secure quote links, and create professional PDFs.",
    url: "https://www.quoteflowai.in/",
    siteName: "QuoteFlow AI",
    type: "website",
  },
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
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
