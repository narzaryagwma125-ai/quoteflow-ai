export type QuoteStatus =
  | "draft"
  | "sent"
  | "viewed"
  | "accepted"
  | "rejected"
  | "expired"
  | "cancelled";

export type Plan = "free" | "starter" | "pro" | "business";

export type CurrencyCode = "USD" | "CAD" | "INR" | "GBP" | "AUD";

export type LogoPosition = "left" | "center" | "right";

export type LogoSize = "small" | "medium" | "large";

export interface User {
  id: number;
  email: string;
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
}

export interface Me {
  id: number;
  email: string;
  is_email_verified: boolean;
  plan: Plan;
  subscription_status: string;
  has_business_profile: boolean;
  trial_active: boolean;
  trial_expired: boolean;
  trial_days_remaining: number;
  trial_expires_at: string | null;
  trial_unlimited: boolean;
}

export interface BusinessProfile {
  id: number;
  business_name: string;
  owner_name: string;
  email: string;
  phone: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state_or_province: string;
  postal_code: string;
  country: string;
  currency: string;
  timezone: string;
  tax_rate_percent: string;
  tax_rate_unconfigured: boolean;
  has_logo: boolean;
  logo_position: LogoPosition;
  logo_size: LogoSize;
  show_logo_on_quotation: boolean;
  created_at: string;
}

export type BuiltinTemplateType = "classic" | "modern" | "minimal" | "executive" | "creative";

export interface TemplateSettings {
  template_type: BuiltinTemplateType | "default" | "custom_docx";
  custom_docx_file_id: number | null;
  custom_docx_filename: string;
  custom_docx_mime_type: string;
  custom_docx_size: number;
  custom_docx_uploaded_at: string | null;
  custom_docx_version: number;
  has_custom_template: boolean;
}

export interface Customer {
  id: number;
  name: string;
  email: string;
  phone: string;
  address: string;
  notes: string;
  created_at: string;
  updated_at: string;
  quote_count?: number;
  total_quoted_minor?: number;
}

export interface QuoteItem {
  id?: number;
  description: string;
  quantity: string;
  unit: string;
  unit_price_minor: number;
  line_total_minor: number;
  sort_order: number;
}

export interface QuoteItemInput {
  description: string;
  quantity: string;
  unit: string;
  unit_price: string;
  sort_order: number;
}

export interface QuoteBreakdown {
  subtotal_minor: number;
  discount_minor: number;
  tax_minor: number;
  total_minor: number;
  tax_rate_percent: string;
}

export interface Quote {
  id: number;
  quote_number: string;
  customer_id: number | null;
  status: QuoteStatus;
  issue_date: string;
  expiry_date: string | null;
  currency: string;
  subtotal_minor: number;
  discount_minor: number;
  tax_minor: number;
  total_minor: number;
  notes: string;
  terms: string;
  created_at: string;
  updated_at: string;
  items: QuoteItem[];
  breakdown: QuoteBreakdown | null;
  customer_name: string;
  public_link_token: string;
  has_public_link: boolean;
}

export interface QuoteResponse {
  quote: Quote;
  public_link: string | null;
}

export interface CurrencyTotal {
  currency: string;
  currency_symbol: string;
  count: number;
  subtotal_minor: number;
  discount_minor: number;
  tax_minor: number;
  total_minor: number;
}

export interface QuoteStats {
  draft: number;
  sent: number;
  viewed: number;
  accepted: number;
  rejected: number;
  expired: number;
  cancelled: number;
  total: number;
  created_this_month: number;
  totals_by_currency: CurrencyTotal[];
}

export interface SubscriptionInfo {
  plan: Plan;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  quotes_used: number;
  quotes_limit: number | null;
  quotes_remaining: number | null;
  ai_used: number;
  ai_limit: number;
  ai_remaining: number;
  trial_active: boolean;
  trial_expired: boolean;
  trial_days_remaining: number;
  trial_expires_at: string | null;
  trial_unlimited: boolean;
}

export interface PublicQuote {
  business_name: string;
  quote_number: string;
  status: QuoteStatus;
  issue_date: string;
  expiry_date: string | null;
  currency: string;
  subtotal_minor: number;
  discount_minor: number;
  tax_minor: number;
  total_minor: number;
  notes: string;
  terms: string;
  items: {
    description: string;
    quantity: string;
    unit: string;
    unit_price_minor: number;
    line_total_minor: number;
  }[];
  may_respond: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}