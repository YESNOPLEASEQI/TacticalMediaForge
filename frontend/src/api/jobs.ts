import { queryOptions } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { GlobalJob, JobAcceptedResponse } from "@/types/jobs";
import type { VideoGenerateRequest } from "@/types/api";

export interface ScriptJobRequest {
  project_id: string;
  text: string;
  n_scenes: number;
  min_words: number;
  max_words: number;
  mode: "reference" | "quick";
}

export interface StoryboardJobRequest {
  project_id: string;
  narrations: string[];
  min_words: number;
  max_words: number;
  asset_type: "image" | "video";
}

export function startScriptJob(request: ScriptJobRequest) {
  return apiClient.post<JobAcceptedResponse, ScriptJobRequest>("/api/content/narration/async", request);
}

export function startStoryboardJob(request: StoryboardJobRequest) {
  return apiClient.post<JobAcceptedResponse, StoryboardJobRequest>("/api/content/image-prompt/async", request);
}

export async function startVideoJob(request: VideoGenerateRequest): Promise<JobAcceptedResponse> {
  const response = await apiClient.post<{ task_id: string }, VideoGenerateRequest>("/api/video/generate/async", request);
  return { job_id: response.task_id };
}

export function stopJob(jobId: string) {
  return apiClient.delete<{ success: boolean; message: string }>(`/api/tasks/${jobId}`);
}

export const jobQueries = {
  global: () => queryOptions({
    queryKey: ["jobs", "global"],
    queryFn: () => apiClient.get<GlobalJob[]>("/api/jobs?limit=200"),
    refetchInterval: 2_000,
    staleTime: 0,
  }),
  project: (projectId: string) => queryOptions({
    queryKey: ["jobs", projectId],
    queryFn: () => apiClient.get<GlobalJob[]>(`/api/projects/${encodeURIComponent(projectId)}/jobs`),
    staleTime: 0,
  }),
};
