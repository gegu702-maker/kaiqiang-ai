export type TaskStatus =
  | "waiting"
  | "generating_script"
  | "cloning_voice"
  | "generating_voice"
  | "generating_avatar"
  | "rendering"
  | "success"
  | "pending"
  | "scripting"
  | "producing"
  | "processing"
  | "completed"
  | "failed";
export type CosyVoiceStatus = "pending" | "generating" | "completed" | "failed";

export type SellingPoint = {
  index: number;
  point: string;
  consumer_benefit: string;
  proof_angle: string;
};

export type ShotItem = {
  index: number;
  duration: string;
  scene: string;
  camera: string;
  action: string;
  narration: string;
  visual_prompt: string;
  tool_suggestion: string;
};

export type WorkflowItem = {
  step: number;
  tool: string;
  action: string;
};

export type VideoTask = {
  id: string;
  user_id: string | null;
  user_email: string;
  product_name: string;
  script: string;
  language: string;
  image_url: string;
  personal_image_url: string | null;
  product_highlights: string;
  target_audience: string;
  video_style: string;
  use_digital_human: boolean;
  production_mode: string;
  avatar_id: string;
  avatar_template_id: string;
  avatar_template_name: string;
  avatar_template_image: string;
  voice_url: string;
  voice_clone_id: string | null;
  use_cloned_voice: boolean;
  tts_language: "zh" | "en";
  tts_voice_name: string;
  admin_notes: string;
  status: TaskStatus;
  result_video_url: string | null;
  output_video_url: string | null;
  subtitle_url: string | null;
  subtitle_status: "pending" | "completed" | "failed";
  cloned_voice_url: string | null;
  voice_duration: number | null;
  talking_video_url: string | null;
  generation_error: string;
  cosyvoice_status: CosyVoiceStatus;
  heygen_avatar_id: string;
  heygen_voice_id: string;
  heygen_video_id: string;
  heygen_video_url: string;
  selling_points: SellingPoint[];
  hook: string;
  shot_list: ShotItem[];
  title_options: string[];
  caption: string;
  cover_text: string;
  cover_prompt: string;
  hashtags: string[];
  comment_prompt: string;
  closing_cta: string;
  admin_workflow: WorkflowItem[];
  queue_id: string | null;
  queue_status: string | null;
  queue_attempts: number;
  queue_error_message: string;
  queue_updated_at: string | null;
  created_at: string;
};

export type ActionState = {
  ok: boolean;
  message: string;
  audioUrl?: string;
  cosyvoiceStatus?: CosyVoiceStatus;
};

export type PlanCode = "free" | "plus" | "pro" | "business";

export type UsageSummary = {
  plan: PlanCode;
  monthly_quota: number | null;
  used: number;
  remaining: number | null;
  period_start: string;
  voice_clone_enabled: boolean;
  default_voice_id: string | null;
};

export type OrderStatus = "pending" | "paid" | "failed" | "refunded";
export type PaymentProvider = "wechat" | "alipay" | "pingpp" | "stripe" | "paypal" | "lemon_squeezy" | "creem" | "manual";

export type Order = {
  id: string;
  user_id: string;
  plan: PlanCode;
  currency: "CNY" | "USD";
  amount: number;
  provider: PaymentProvider;
  status: OrderStatus;
  billing_cycle: "monthly" | "yearly";
  metadata: Record<string, unknown>;
  created_at: string;
};

export type UsageLog = {
  id: string;
  user_id: string;
  task_id: string | null;
  action: string;
  quantity: number;
  period_start: string;
  created_at: string;
};

export type AdminUser = {
  id: string;
  email: string;
  plan: PlanCode;
  monthly_quota: number | null;
  custom_quota: number | null;
  voice_clone_enabled: boolean;
  default_voice_id: string | null;
  voice_clone_count: number;
  status: "active" | "banned";
  created_at: string;
};

export type AdminStats = {
  total_users: number;
  free_users: number;
  business_users: number;
  waitlist_count: number;
  avatar_generations: number;
  today_generations: number;
  today_registrations: number;
  supabase_service_role_key_configured: boolean;
};

export type CheckoutResponse = {
  order: Order;
  checkout_url: string | null;
  provider_status: "created" | "not_configured" | "manual_review" | "pending";
  payment_status: OrderStatus;
  message: string;
};

export type VoiceClone = {
  id: string;
  user_id: string;
  provider: "mock" | "elevenlabs" | "minimax" | "fishaudio" | "openvoice" | "volcengine";
  voice_id: string;
  name: string;
  sample_audio_url: string;
  status: "uploaded" | "pending" | "ready" | "completed" | "failed" | "deleted";
  created_at: string;
};
