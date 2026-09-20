import { describe, expect, it } from "vitest";
import {
  businessProfileSchema,
  contactSchema,
  customerSchema,
  loginSchema,
  quoteItemSchema,
  resetPasswordSchema,
  signupSchema,
} from "@/lib/validation";

describe("signupSchema", () => {
  it("accepts a valid signup", () => {
    const r = signupSchema.safeParse({ email: "a@b.com", password: "correct horse battery" });
    expect(r.success).toBe(true);
  });

  it("rejects a short password", () => {
    const r = signupSchema.safeParse({ email: "a@b.com", password: "short" });
    expect(r.success).toBe(false);
  });

  it("rejects an invalid email", () => {
    const r = signupSchema.safeParse({ email: "nope", password: "correct horse battery" });
    expect(r.success).toBe(false);
  });
});

describe("loginSchema", () => {
  it("requires both fields", () => {
    expect(loginSchema.safeParse({ email: "a@b.com", password: "x" }).success).toBe(true);
    expect(loginSchema.safeParse({ email: "a@b.com", password: "" }).success).toBe(false);
  });
});

describe("resetPasswordSchema", () => {
  it("requires a long enough token and strong password", () => {
    expect(
      resetPasswordSchema.safeParse({ token: "x".repeat(16), password: "correct horse battery" }).success,
    ).toBe(true);
    expect(resetPasswordSchema.safeParse({ token: "short", password: "correct horse battery" }).success).toBe(false);
    expect(resetPasswordSchema.safeParse({ token: "x".repeat(16), password: "short" }).success).toBe(false);
  });
});

describe("businessProfileSchema", () => {
  it("accepts a complete profile", () => {
    const r = businessProfileSchema.safeParse({
      business_name: "Sparkle",
      owner_name: "A",
      email: "a@b.com",
      country: "US",
      currency: "USD",
      timezone: "America/New_York",
      tax_rate: "7.5",
      logo_position: "left",
      logo_size: "medium",
      show_logo_on_quotation: true,
    });
    expect(r.success).toBe(true);
  });

  it("rejects bad country and tax", () => {
    const base = {
      business_name: "B",
      owner_name: "O",
      email: "a@b.com",
      timezone: "UTC",
    };
    expect(businessProfileSchema.safeParse({ ...base, country: "MX", currency: "USD", tax_rate: "7.5" }).success).toBe(false);
    expect(businessProfileSchema.safeParse({ ...base, country: "US", currency: "USD", tax_rate: "7.555" }).success).toBe(false);
  });

  it("accepts all supported currencies and rejects unsupported ones", () => {
    const base = {
      business_name: "B",
      owner_name: "O",
      email: "a@b.com",
      country: "US",
      timezone: "UTC",
      tax_rate: "7.5",
      logo_position: "left",
      logo_size: "medium",
      show_logo_on_quotation: true,
    };
    for (const currency of ["USD", "CAD", "INR", "GBP", "AUD"]) {
      expect(businessProfileSchema.safeParse({ ...base, currency }).success).toBe(true);
    }
    expect(businessProfileSchema.safeParse({ ...base, currency: "EUR" }).success).toBe(false);
  });
});

describe("customerSchema", () => {
  it("requires a name", () => {
    expect(customerSchema.safeParse({ name: "ACME" }).success).toBe(true);
    expect(customerSchema.safeParse({ name: "" }).success).toBe(false);
  });
});

describe("quoteItemSchema", () => {
  it("requires positive quantity and valid price", () => {
    const ok = { description: "D", quantity: "2.5", unit: "hr", unit_price: "40.00" };
    expect(quoteItemSchema.safeParse(ok).success).toBe(true);
    expect(quoteItemSchema.safeParse({ ...ok, quantity: "-1" }).success).toBe(false);
    expect(quoteItemSchema.safeParse({ ...ok, unit_price: "40.123" }).success).toBe(false);
  });
});

describe("contactSchema", () => {
  const base = {
    name: "Jane Customer",
    email: "jane@example.com",
    subject: "Subscription & billing",
    message: "This is a message with enough detail to send.",
  };

  it("accepts a valid contact message", () => {
    expect(contactSchema.safeParse(base).success).toBe(true);
  });

  it("rejects an invalid email", () => {
    const r = contactSchema.safeParse({ ...base, email: "not-an-email" });
    expect(r.success).toBe(false);
  });

  it("rejects a missing name", () => {
    expect(contactSchema.safeParse({ ...base, name: "" }).success).toBe(false);
    expect(contactSchema.safeParse({ ...base, name: "   " }).success).toBe(false);
  });

  it("rejects a message that is too short or blank after trimming", () => {
    expect(contactSchema.safeParse({ ...base, message: "short" }).success).toBe(false);
    expect(contactSchema.safeParse({ ...base, message: "          " }).success).toBe(false);
  });

  it("rejects a missing subject", () => {
    expect(contactSchema.safeParse({ ...base, subject: "" }).success).toBe(false);
  });
});