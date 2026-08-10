import type { SessionDetail, SessionSummary } from "@/types/history";
import type { VideoWorkflowDraft } from "@/features/video/workflow";
import type { GlobalJobType } from "@/types/jobs";

export type ProjectStage = "script" | "storyboard" | "video" | "output";

export interface Project {
  id: string;
  title: string;
  description: string | null;
  project_type: string;
  status: string;
  current_stage: string | null;
  source_text: string | null;
  thumbnail_path: string | null;
  owner_id: string | null;
  settings_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  deleted_at: string | null;
}

export interface ProjectCreate {
  title: string;
  description?: string | null;
  project_type?: string;
  status?: string;
  current_stage?: string | null;
  source_text?: string | null;
  settings_json?: Record<string, unknown>;
}

export interface ProjectUpdate {
  title?: string;
  description?: string | null;
  project_type?: string;
  status?: string;
  current_stage?: string | null;
  source_text?: string | null;
  thumbnail_path?: string | null;
  owner_id?: string | null;
  settings_json?: Record<string, unknown>;
  archived_at?: string | null;
}

export interface ProjectCardData extends Project {
  storyboardCount: number;
  latestJobStatus: SessionSummary["status"] | null;
  latestJobId: string | null;
  thumbnailUrl: string | null;
  videoUrl: string | null;
  session: SessionSummary | null;
  latestJobType?: GlobalJobType | null;
  latestJobProgress?: number | null;
  latestJobCurrentScene?: number | null;
  latestJobTotalScenes?: number | null;
  hasUnsubmittedChanges?: boolean;
}

export interface ProjectWorkspace {
  project: Project;
  history: SessionDetail | null;
}

export interface ProjectDraftSettings {
  workspace_draft?: VideoWorkflowDraft;
  workspace_draft_updated_at?: string;
  legacy_session_id?: string;
  active_research_job_id?: string;
}
