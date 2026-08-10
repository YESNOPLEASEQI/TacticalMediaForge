export type HistoryStatus = "queued" | "running" | "success" | "failed" | "cancelled";
export type MessageRole = "user" | "assistant" | "system" | "tool";
export type AssetType = "video" | "image" | "audio" | "subtitle" | "workflow" | "preview" | "mask";

export interface SessionSummary {
  id: string;
  title: string;
  user_id?: string | null;
  project_type: string;
  status: HistoryStatus;
  job_count: number;
  latest_job_id?: string | null;
  thumbnail_url?: string | null;
  video_url?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface HistoryMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: {
    text?: string;
    attachments?: unknown[];
    intent?: string;
    agentSummary?: string;
    scenes?: HistoryScene[];
    [key: string]: unknown;
  };
  created_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface HistoryScene {
  index: number;
  narration: string;
  image_prompt: string;
  visual_description?: string;
  media_prompt?: string;
  duration?: number;
  estimated_duration?: number;
  asset_type?: "image" | "video";
  media_type?: "image" | "video";
  status?: "draft" | "queued" | "running" | "completed" | "failed";
  research_job_id?: string | null;
  subject_id?: string | null;
  claim_ids?: string[];
  visual_fact_ids?: string[];
  field_provenance?: Record<string, import("@/types/api").FieldProvenance>;
  fallback_level?: import("@/types/api").FallbackLevel;
  verification_status?: import("@/types/api").VerificationStatus;
  negative_constraints?: string[];
  warnings?: string[];
  reference_asset_ids?: string[];
}

export interface GenerationJob {
  id: string;
  session_id: string;
  message_id?: string | null;
  status: HistoryStatus;
  progress: number;
  provider: string;
  external_job_id?: string | null;
  prompt: string;
  negative_prompt?: string | null;
  model_name?: string | null;
  workflow_id?: string | null;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
  fps?: number | null;
  seed?: number | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  completed_at?: string | null;
  params: Record<string, unknown>;
  result: Record<string, unknown>;
}

export interface HistoryAsset {
  id: string;
  job_id: string;
  session_id: string;
  asset_type: AssetType;
  url?: string | null;
  local_path?: string | null;
  thumbnail_url?: string | null;
  filename?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
  created_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface WorkflowSnapshot {
  id: string;
  job_id: string;
  session_id: string;
  workflow_name: string;
  workflow_json: Record<string, unknown>;
  ui_json: Record<string, unknown>;
  created_at?: string | null;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
  total: number;
}

export interface SessionDetail {
  session: SessionSummary;
  messages: HistoryMessage[];
  generation_jobs: GenerationJob[];
  assets: HistoryAsset[];
  workflow_snapshots: WorkflowSnapshot[];
}

export interface RetryJobResponse {
  params: Record<string, unknown>;
}
