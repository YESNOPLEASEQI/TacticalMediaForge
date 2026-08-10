export type GlobalJobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type GlobalJobType = "script_generation" | "storyboard_generation" | "video_generation" | "research";

export interface GlobalJob {
  id: string;
  project_id: string;
  parent_job_id?: string | null;
  job_type: GlobalJobType;
  provider: string;
  status: GlobalJobStatus;
  progress: number;
  external_job_id: string | null;
  workflow_id?: string | null;
  model_name?: string | null;
  params_json: Record<string, unknown>;
  result_json: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  progress_stage?: string | null;
  progress_message?: string | null;
  progress_current_scene?: number | null;
  progress_total_scenes?: number | null;
}

export interface JobAcceptedResponse {
  job_id: string;
}
