import { apiClient } from "@/api/client";
import type { JobAcceptedResponse } from "@/types/jobs";

export interface ResearchJobRequest {
  project_id: string;
  topic: string;
  narrations: string[];
  asset_type: "image" | "video";
  mode: "verified";
  script_revision: number;
  force_refresh?: boolean;
}

export interface ResearchDependencyDiagnostic {
  status: "reachable" | "unreachable" | "not_checked";
  latency_ms: number | null;
  error: string | null;
}

export interface ResearchMonitorEvent {
  timestamp: string;
  event: string;
  status: string;
  job_id: string | null;
  project_id: string | null;
  phase: string | null;
  message: string | null;
  metrics: Record<string, string | number | boolean>;
}

export interface ResearchDiagnostics {
  status: "ready" | "degraded" | "disabled";
  enabled: boolean;
  default_mode: "verified";
  token_configured: boolean;
  services: {
    searxng: ResearchDependencyDiagnostic;
    crawl4ai: ResearchDependencyDiagnostic;
  };
  recent_events: ResearchMonitorEvent[];
}

export function getResearchDiagnostics() {
  return apiClient.get<ResearchDiagnostics>("/api/content/research/diagnostics");
}

export function startResearchJob(request: ResearchJobRequest) {
  return apiClient.post<JobAcceptedResponse, ResearchJobRequest>(
    "/api/content/research/async",
    request,
  );
}

export function retryResearchJob(jobId: string, request?: ResearchJobRequest, forceRefresh = true) {
  return apiClient.post<JobAcceptedResponse, { parent_job_id: string; force_refresh: boolean; request?: ResearchJobRequest }>(
    `/api/content/research/${encodeURIComponent(jobId)}/retry`,
    { parent_job_id: jobId, force_refresh: forceRefresh, request },
  );
}
