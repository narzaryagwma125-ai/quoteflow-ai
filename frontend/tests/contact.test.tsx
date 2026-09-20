import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next/navigation", () => ({
  usePathname: () => "/contact",
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

import ContactPage from "@/app/contact/page";

type Res = {
  ok: boolean;
  status: number;
  headers: { get: (name: string) => string | null };
  json: () => Promise<unknown>;
};

function jsonResponse(status: number, body: unknown): Res {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (n) => (n.toLowerCase() === "content-type" ? "application/json" : null) },
    json: async () => body,
  };
}

function stubFetch(response: Res) {
  const fetchMock = vi.fn((_input: RequestInfo | URL, _init?: RequestInit) =>
    Promise.resolve(response as unknown as Response),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const validValues = {
  name: "Jane Customer",
  email: "jane@example.com",
  subject: "Subscription & billing",
  message: "My card was charged twice last month. Please help.",
};

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, overrides: Partial<typeof validValues> = {}) {
  const values = { ...validValues, ...overrides };
  await user.type(await screen.findByLabelText("Name"), values.name);
  await user.type(screen.getByLabelText("Email"), values.email);
  await user.selectOptions(screen.getByLabelText("Subject"), values.subject);
  await user.type(screen.getByLabelText("Message"), values.message);
  await user.click(screen.getByRole("button", { name: "Send message" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

describe("contact page", () => {
  it("shows field errors for invalid input and never calls the API", async () => {
    const fetchMock = stubFetch(jsonResponse(200, { message: "ok" }));
    const user = userEvent.setup();

    render(<ContactPage />);
    await fillAndSubmit(user, { email: "not-an-email", message: "short" });

    expect(await screen.findByText("Enter a valid email.")).toBeInTheDocument();
    expect(screen.getByText("Message must be at least 10 characters.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("requires all fields before submitting", async () => {
    const fetchMock = stubFetch(jsonResponse(200, { message: "ok" }));
    const user = userEvent.setup();

    render(<ContactPage />);
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByText("Enter your name.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid email.")).toBeInTheDocument();
    expect(screen.getByText("Choose a subject.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends a valid message and shows the success state", async () => {
    const fetchMock = stubFetch(jsonResponse(200, { message: "Thank you!" }));
    const user = userEvent.setup();

    render(<ContactPage />);
    await fillAndSubmit(user);

    expect(await screen.findByText("Message sent")).toBeInTheDocument();
    expect(screen.getByText(/We've received your message/)).toBeInTheDocument();

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/contact$/);
    const body = JSON.parse(String(init?.body));
    expect(body.name).toBe("Jane Customer");
    expect(body.email).toBe("jane@example.com");
    expect(body.subject).toBe("Subscription & billing");
    expect(body.message).toBe(validValues.message);
    expect(body.website).toBe(""); // honeypot stays empty
  });

  it("surfaces API errors without crashing", async () => {
    stubFetch(jsonResponse(503, { detail: "Server hiccup" }));
    const user = userEvent.setup();

    render(<ContactPage />);
    await fillAndSubmit(user);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    // api() maps 5xx to a generic, server-detail-free message.
    expect(screen.getByText("The server hit an unexpected error. Please try again in a moment.")).toBeInTheDocument();
    expect(screen.queryByText("Server hiccup")).not.toBeInTheDocument();
  });

  it("recovers after being declined by the server", async () => {
    stubFetch(jsonResponse(400, { detail: "Too many requests." }));
    const user = userEvent.setup();

    render(<ContactPage />);
    await fillAndSubmit(user);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Too many requests.")).toBeInTheDocument();
  });
});