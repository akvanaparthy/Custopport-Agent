// Mirrors the backend's frozen contracts (one source of truth across layers).

export type Decision = "APPROVE" | "DENY" | "ESCALATE";
export type IdentityMode = "authenticated" | "in_chat";
export type Effort = "low" | "medium" | "high" | "max";

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
}

export interface Session {
  session_id: string;
  identity_mode: IdentityMode;
  customer_id: string | null;
  verified: number; // 0 | 1
  created_at: string;
  last_seen: string;
}

export interface SettingsView {
  model: string;
  effort: Effort;
  adaptive_thinking: boolean;
  max_tokens: number;
  input_guard_enabled: boolean;
  output_validation_enabled: boolean;
  identity_mode: IdentityMode;
  persona: string;
  source_map: Record<string, "env" | "override">;
}

export interface OrderView {
  order_id: string;
  customer_id: string;
  item_name: string;
  category: string;
  order_total: number;
  currency: string;
  status: string;
  order_date: string;
  delivered_date: string | null;
  is_final_sale: boolean;
  item_condition: string;
  already_refunded: boolean;
  refunded_amount: number;
  refunded_at: string | null;
}

export type StepType =
  | "input_guard"
  | "llm"
  | "tool"
  | "policy_engine"
  | "action"
  | "output_validation";

export interface StepView {
  step_index: number;
  step_type: StepType;
  name: string;
  status: "ok" | "error";
  input: unknown;
  output: unknown;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cost_usd: number;
  latency_ms: number;
  retry_count: number;
  attempts: unknown;
  error: unknown;
  started_at: string;
}

export interface RunSummary {
  run_id: string;
  conversation_id: string;
  identity_mode: string;
  customer_id: string | null;
  model: string;
  final_verdict: Decision | null;
  status: "running" | "completed" | "error";
  total_cost_usd: number;
  total_latency_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  step_count: number;
  started_at: string;
  finished_at: string | null;
}

export interface RunDetail extends RunSummary {
  steps: StepView[];
}

export interface OrderHint {
  tone: "eligible" | "review" | "blocked" | "refunded";
  label: string;
}

export interface CustomerOrder {
  order_id: string;
  item_name: string;
  category: string;
  order_total: number;
  currency: string;
  status: string;
  order_date: string;
  delivered_date: string | null;
  is_final_sale: boolean;
  item_condition: string;
  already_refunded: boolean;
  refunded_amount: number;
  hint: OrderHint;
}

// SSE payloads from POST /api/chat
export interface VerdictEvent {
  decision: Decision;
  policy_refs: string[];
}
export interface FinalMessageEvent {
  message: string;
  outcome: string;
  run_id: string;
  conversation_id: string;
}
