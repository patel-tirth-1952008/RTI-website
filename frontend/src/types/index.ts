export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  city?: string;
  state?: string;
  role: string;
  is_verified: boolean;
  is_bpl: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RTIApplication {
  tracking_number: string;
  portal_reference_number?: string;
  status: string;
  category: string;
  department_name?: string;
  filing_date?: string;
  response_due_date?: string;
  response_received_date?: string;
  response_summary?: string;
  days_remaining?: number;
  created_at: string;
  updated_at: string;
}

export interface RTIGenerateResponse {
  tracking_number: string;
  status: string;
  category: string;
  department_type?: string;
  department_name?: string;
  pio_name?: string;
  pio_address?: string;
  generated_subject: string;
  generated_body: string;
  generated_questions: string[];
  generated_pdf_url?: string;
  ai_category_confidence?: number;
  ai_department_confidence?: number;
  image_authenticity_score?: number;
  estimated_fee: number;
  portal_url?: string;
  created_at: string;
}

export interface FraudCheckResult {
  overall_result: string;
  overall_score: number;
  checks: Array<{
    check_type: string;
    result: string;
    confidence: number;
    details: Record<string, unknown>;
  }>;
  recommendation: string;
}

export type IssueCategory =
  | "road_repair"
  | "water_supply"
  | "electricity"
  | "sanitation"
  | "education"
  | "healthcare"
  | "corruption"
  | "government_scheme"
  | "land_records"
  | "police"
  | "environment"
  | "public_transport"
  | "general";