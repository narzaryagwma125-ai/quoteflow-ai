import { afterEach, describe, expect, it, vi } from "vitest";
import { api, apiBlob, ApiError } from "@/lib/api";

type FetchStub = {
  ok: boolean;
  status: number;
  headers: { get: (name: string) => string | null };
  json: () => Promise<unknown>;
};

function stubResponse(
  status: number,
  body: unknown,
  contentType = "application/json",
): FetchStub {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === "content-type" ? contentType : null,
    },
    json: async () => body,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api error handling", () => {
  it("uses a string detail from an HTTP 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(stubResponse(400, { detail: "Could not create account." })),
    );
    await expect(api("/auth/signup", { method: "POST" })).rejects.toMatchObject({
      status: 400,
      message: "Could not create account.",
    });
  });

  it("extracts the first message from an array detail (HTTP 422 validation)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        stubResponse(422, {
          detail: [
            {
              loc: ["body", "password"],
              msg: "String should have at least 10 characters",
              type: "string_too_short",
            },
          ],
        }),
      ),
    );
    await expect(api("/auth/signup", { method: "POST" })).rejects.toMatchObject({
      status: 422,
      message: "String should have at least 10 characters",
    });
  });

  it("handles an array detail whose first entry is a plain string", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(stubResponse(404, { detail: ["not found"] })),
    );
    await expect(api("/unknown", {})).rejects.toMatchObject({
      status: 404,
      message: "not found",
    });
  });

  it("falls back to a readable message when detail/errors are missing (HTTP 500)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(stubResponse(500, { detail: undefined })),
    );
    await expect(api("/quotes", {})).rejects.toMatchObject({
      status: 500,
      message: "The server hit an unexpected error. Please try again in a moment.",
    });
  });

  it("falls back to a readable message when the body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(stubResponse(500, "<html>boom</html>", "text/html")),
    );
    await expect(api("/quotes", {})).rejects.toMatchObject({
      status: 500,
      message: "The server hit an unexpected error. Please try again in a moment.",
    });
  });

  it("reads a message field when errors is undefined", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(stubResponse(400, { errors: undefined, message: "Nope." })),
    );
    await expect(api("/me", {})).rejects.toMatchObject({
      status: 400,
      message: "Nope.",
    });
  });

  it("throws ApiError instances with the response status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(stubResponse(400, { detail: "x" })),
    );
    const err = (await api("/x", {}).catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
  });

  it("propagates successful responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        stubResponse(200, { user: { is_email_verified: true } }),
      ),
    );
    const data = await api<{ user: { is_email_verified: boolean } }>("/me", {});
    expect(data.user.is_email_verified).toBe(true);
  });
});

describe("apiBlob", () => {
  it("returns a Blob on success", async () => {
    const fakeBlob = new Blob(["PDF content"], { type: "application/pdf" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        blob: async () => fakeBlob,
        headers: { get: () => "application/pdf" },
      }),
    );
    const result = await apiBlob("/quotes/1/generate-pdf", { method: "POST" });
    expect(result).toBeInstanceOf(Blob);
    expect(result.size).toBe(11);
  });

  it("throws ApiError on non-ok response with JSON detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        headers: { get: (n: string) => n.toLowerCase() === "content-type" ? "application/json" : null },
        json: async () => ({ detail: "Quote not found." }),
      }),
    );
    await expect(
      apiBlob("/quotes/999/pdf"),
    ).rejects.toMatchObject({ status: 404, message: "Quote not found." });
  });
});