import { z } from "zod";

export const signupSchema = z.object({
  email: z.string().email("Enter a valid email."),
  password: z
    .string()
    .min(10, "Password must be at least 10 characters.")
    .max(200, "Password is too long."),
});

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email."),
  password: z.string().min(1, "Enter your password."),
});

export const forgotPasswordSchema = z.object({
  email: z.string().email("Enter a valid email."),
});

export const resetPasswordSchema = z.object({
  token: z.string().min(16, "Invalid reset link."),
  password: z
    .string()
    .min(10, "Password must be at least 10 characters.")
    .max(200, "Password is too long."),
});

export const businessProfileSchema = z.object({
  business_name: z.string().min(1, "Business name is required.").max(200),
  owner_name: z.string().min(1, "Owner name is required.").max(200),
  email: z.string().email("Enter a valid email."),
  phone: z.string().max(40).optional().or(z.literal("")),
  address_line_1: z.string().max(255).optional().or(z.literal("")),
  address_line_2: z.string().max(255).optional().or(z.literal("")),
  city: z.string().max(120).optional().or(z.literal("")),
  state_or_province: z.string().max(120).optional().or(z.literal("")),
  postal_code: z.string().max(20).optional().or(z.literal("")),
  country: z.enum(["US", "CA"]),
  currency: z.enum(["USD", "CAD", "INR", "GBP", "AUD"]),
  timezone: z.string().max(64),
  tax_rate: z
    .string()
    .regex(/^\d+(\.\d{1,2})?$/, "Enter a valid tax rate percentage, e.g. 7.5")
    .max(20),
  logo_position: z.enum(["left", "center", "right"]),
  logo_size: z.enum(["small", "medium", "large"]),
  show_logo_on_quotation: z.boolean(),
});

export const customerSchema = z.object({
  name: z.string().min(1, "Name is required.").max(200),
  email: z
    .string()
    .email("Enter a valid email.")
    .optional()
    .or(z.literal(""))
    .or(z.literal(undefined)),
  phone: z.string().max(40).optional().or(z.literal("")),
  address: z.string().max(2000).optional().or(z.literal("")),
  notes: z.string().max(4000).optional().or(z.literal("")),
});

export const quoteItemSchema = z.object({
  description: z.string().min(1, "Description is required.").max(4000),
  quantity: z.string().regex(/^\d+(\.\d{1,3})?$/, "Enter a positive quantity."),
  unit: z.string().max(20).optional().or(z.literal("")),
  unit_price: z.string().regex(/^\d+(\.\d{1,2})?$/, "Enter a price like 149.99"),
});

export const quoteSchema = z.object({
  customer_id: z.number().nullable().optional(),
  issue_date: z.string().min(1, "Issue date is required."),
  expiry_date: z.string().optional().nullable(),
  currency: z.enum(["USD", "CAD", "INR", "GBP", "AUD"]),
  discount: z.string().regex(/^\d+(\.\d{1,2})?$/, "Enter a valid discount."),
  notes: z.string().max(10000).optional().or(z.literal("")),
  terms: z.string().max(10000).optional().or(z.literal("")),
  items: z.array(quoteItemSchema).min(1, "Add at least one service item.").max(50),
});

export const contactSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Enter your name.")
    .max(120, "Name is too long."),
  email: z
    .string()
    .trim()
    .toLowerCase()
    .email("Enter a valid email."),
  subject: z
    .string()
    .trim()
    .min(1, "Choose a subject.")
    .max(200, "Subject is too long."),
  message: z
    .string()
    .trim()
    .min(10, "Message must be at least 10 characters.")
    .max(5000, "Message is too long."),
  website: z.string().max(500).optional().or(z.literal("")),
});

export type SignupInput = z.infer<typeof signupSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;
export type BusinessProfileInput = z.infer<typeof businessProfileSchema>;
export type QuoteItemInputZod = z.infer<typeof quoteItemSchema>;
export type QuoteInput = z.infer<typeof quoteSchema>;
export type ContactInput = z.infer<typeof contactSchema>;