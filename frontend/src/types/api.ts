export interface HealthResponse {
  status?: string;
  service?: string;
  version?: string;
  research_enabled?: boolean;
  research_default_mode?: "verified";
  [key: string]: unknown;
}

export interface TemplateInfo {
  name: string;
  display_name: string;
  size: string;
  width: number;
  height: number;
  orientation: "portrait" | "landscape" | "square" | string;
  path: string;
  key: string;
}

export interface TemplateListResponse {
  success: boolean;
  message: string;
  templates: TemplateInfo[];
}

export interface BGMInfo {
  name: string;
  path: string;
  source: "default" | "custom" | string;
}

export interface BGMListResponse {
  success: boolean;
  message: string;
  bgm_files: BGMInfo[];
}

export interface WorkflowInfo {
  name?: string;
  key: string;
  display_name?: string;
  source?: string;
  path?: string;
  workflow_id?: string | null;
}

export interface WorkflowListResponse {
  success?: boolean;
  message?: string;
  workflows: WorkflowInfo[];
}

export type VideoMode = "generate" | "fixed";

export type VerificationStatus = "verified" | "low_confidence_verified" | "partial" | "insufficient_evidence" | "unverified";
export type ResearchStatus = "researching" | "reference_ready" | "partial_reference" | "reference_unavailable" | "quick";
export type FallbackLevel = "verified_specific" | "verified_generic" | "generic_safe" | "insufficient_evidence" | "unverified";

export interface FieldProvenance {
  claim_ids: string[];
  visual_fact_ids: string[];
  creative: boolean;
}

export interface ConfirmedStoryboardScene {
  index: number;
  narration: string;
  visual_description: string;
  media_prompt: string;
  estimated_duration: number;
  asset_type: "image" | "video";
  research_job_id?: string | null;
  subject_id?: string | null;
  claim_ids?: string[];
  visual_fact_ids?: string[];
  field_provenance?: Record<string, FieldProvenance>;
  fallback_level?: FallbackLevel;
  verification_status?: VerificationStatus;
  negative_constraints?: string[];
  warnings?: string[];
  reference_asset_ids?: string[];
}

export interface ReferenceAsset {
  id: string;
  project_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  width: number;
  height: number;
  metadata_json: Record<string, unknown>;
  url: string;
  created_at: string;
}

export interface VideoGenerateRequest {
  text: string;
  mode: VideoMode;
  session_id?: string | null;
  confirmed_storyboard?: ConfirmedStoryboardScene[] | null;
  verification_mode?: "verified" | "unverified";
  research_topic?: string | null;
  script_revision?: number | null;
  workflow_revision?: number | null;
  title?: string | null;
  n_scenes?: number;
  min_narration_words: number;
  max_narration_words: number;
  min_image_prompt_words: number;
  max_image_prompt_words: number;
  media_workflow?: string | null;
  tts_workflow?: string | null;
  video_fps: number;
  frame_template: string;
  template_params?: Record<string, unknown> | null;
  prompt_prefix?: string | null;
  bgm_path?: string | null;
  bgm_volume: number;
  reference_mode?: "standard" | "h3";
}

export interface VideoGenerateAsyncResponse {
  success: boolean;
  message: string;
  task_id: string;
}

export interface LLMConfigResponse {
  success: boolean;
  message: string;
  api_key_masked: string;
  has_api_key: boolean;
  base_url: string;
  model: string;
}

export interface LLMConfigUpdateRequest {
  api_key?: string | null;
  base_url: string;
  model: string;
}

export interface LLMModelsRequest {
  api_key?: string | null;
  base_url?: string | null;
}

export interface LLMModelsResponse {
  success: boolean;
  message: string;
  models: string[];
}

export type TaskStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface TaskProgress {
  current: number;
  total: number;
  percentage: number;
  message: string;
  stage?: string | null;
  current_scene?: number | null;
  total_scenes?: number | null;
}

export interface VideoTaskResult {
  video_url?: string;
  duration?: number;
  file_size?: number;
}

export interface Task {
  task_id: string;
  task_type: "script_generation" | "storyboard_generation" | "video_generation" | "research";
  status: TaskStatus;
  progress?: TaskProgress | null;
  result?: (VideoTaskResult & Record<string, unknown>) | null;
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  request_params?: Record<string, unknown> | null;
}
