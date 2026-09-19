import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PublicQuote } from "@/types";

vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "sec-ret-123" }),
}));

import PublicQuotePage from "@/app/q/[token]/page";

type Res = {
  ok: boolean;
  status: number;
  headers: { get: (name: string) => string | null };
  json: () => Promise<unknown>;
  blob: () => Promise<Blob>;
};

function jsonResponse(status: number, body: unknown): Res {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (n) => (n.toLowerCase() === "content-type" ? "application/json" : null) },
    json: async () => body,
    blob: async () => new Blob([JSON.stringify(body)], { type: "application/json" }),
  };
}

function publicQuote(over: Partial<PublicQuote> = {}): PublicQuote {
  return {
    business_name: "Sparkle Cleaning",
    quote_number: "Q-2026-0002",
    status: "sent",
    issue_date: "2026-09-13",
    expiry_date: "2026-10-13",
    currency: "USD",
    subtotal_minor: 10000,
    discount_minor: 0,
    tax_minor: 750,
    total_minor: 10750,
    notes: "",
    terms: "",
    items: [
      { description: "Clean", quantity: "1", unit: "job", unit_price_minor: 10000, line_total_minor: 10000 },
    ],
    may_respond: true,
    ...over,
  };
}

function stubFetch(routes: Array<{ path: string; method?: string; response: Res }>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const route = routes.find((r) => url.endsWith(r.path) && method === (r.method ?? "GET"));
    if (!route) return Promise.reject(new Error(`Unhandled ${method} ${url}`));
    return Promise.resolve(route.response);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

describe("public quote page", () => {
  it("shows the Accept Quote button and no download option before acceptance", async () => {
    stubFetch([{ path: "/public/quotes/sec-ret-123", response: jsonResponse(200, publicQuote()) }]);
    render(<PublicQuotePage />);

    expect(await screen.findByRole("button", { name: "Accept quote" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download Accepted Quote PDF" })).not.toBeInTheDocument();
    expect(screen.queryByText("Quote accepted.")).not.toBeInTheDocument();
    expect(screen.queryByText("DOCX")).not.toBeInTheDocument();
  });

  it("shows Quote accepted and a single accepted-PDF download button after accepting", async () => {
    stubFetch([
      { path: "/public/quotes/sec-ret-123", response: jsonResponse(200, publicQuote()) },
      {
        path: "/public/quotes/sec-ret-123/accept",
        method: "POST",
        response: jsonResponse(200, { message: "Quote accepted.", quote_number: "Q-2026-0002", status: "accepted" }),
      },
    ]);
    const user = userEvent.setup();
    render(<PublicQuotePage />);

    await user.type(await screen.findByLabelText("Your name"), "Jane Smith");
    await user.click(screen.getByRole("button", { name: "Accept quote" }));
    await user.click(screen.getByRole("button", { name: "Accept" }));

    expect(await screen.findByText("Quote accepted.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download Accepted Quote PDF" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept quote" })).not.toBeInTheDocument();
    expect(screen.queryAllByRole("button", { name: /PDF/i })).toHaveLength(1);
    expect(screen.queryByText(/DOCX/i)).not.toBeInTheDocument();
  });

  it("keeps the download button visible after a page refresh (accepted quote)", async () => {
    stubFetch([
      {
        path: "/public/quotes/sec-ret-123",
        response: jsonResponse(200, publicQuote({ status: "accepted", may_respond: false })),
      },
    ]);
    render(<PublicQuotePage />);

    expect(await screen.findByText("Quote accepted.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download Accepted Quote PDF" })).toBeInTheDocument();
  });

  it("downloads the accepted PDF with the exact filename after acceptance", async () => {
    const pdf = new Blob(["%PDF-1.4 accepted"], { type: "application/pdf" });
    const createObjectURL = vi.fn(() => "blob:accepted-pdf");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL }));

    const fetchMock = stubFetch([
      {
        path: "/public/quotes/sec-ret-123",
        response: jsonResponse(200, publicQuote({ status: "accepted", may_respond: false })),
      },
      {
        path: "/public/quotes/sec-ret-123/pdf",
        response: {
          ok: true,
          status: 200,
          headers: { get: (n) => (n.toLowerCase() === "content-type" ? "application/pdf" : null) },
          json: async () => ({}),
          blob: async () => pdf,
        },
      },
    ]);
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const appendSpy = vi.spyOn(document.body, "appendChild");

    const user = userEvent.setup();
    render(<PublicQuotePage />);

    await user.click(await screen.findByRole("button", { name: "Download Accepted Quote PDF" }));

    await vi.waitFor(() => expect(clickSpy).toHaveBeenCalled());
    const pdfCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/public/quotes/sec-ret-123/pdf"));
    expect(pdfCall).toBeTruthy();

    const appended = appendSpy.mock.calls.map(([node]) => node);
    const anchor = appended.find((n): n is HTMLAnchorElement => n instanceof HTMLAnchorElement);
    expect(anchor).toBeDefined();
    expect(anchor?.download).toBe("Q-2026-0002-Accepted.pdf");
    expect(anchor?.href).toBe("blob:accepted-pdf");
  });

  it("surfaces a blocked download as an error without crashing", async () => {
    const user = userEvent.setup();
    stubFetch([
      {
        path: "/public/quotes/sec-ret-123",
        response: jsonResponse(200, publicQuote({ status: "accepted", may_respond: false })),
      },
      {
        path: "/public/quotes/sec-ret-123/pdf",
        response: jsonResponse(400, { detail: "The accepted-quote PDF is only available after the quote is accepted." }),
      },
    ]);

    render(<PublicQuotePage />);
    await user.click(await screen.findByRole("button", { name: "Download Accepted Quote PDF" }));

    expect(
      await screen.findByText(
        "The accepted-quote PDF is only available after the quote is accepted.",
      ),
    ).toBeInTheDocument();
  });
});