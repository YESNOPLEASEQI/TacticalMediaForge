import { queryOptions } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { BGMListResponse, HealthResponse, TemplateListResponse, WorkflowListResponse } from "@/types/api";

export const resourceQueries = {
  health: () =>
    queryOptions({
      queryKey: ["health"],
      queryFn: () => apiClient.get<HealthResponse>("/health"),
      retry: 1,
      refetchInterval: 15_000,
      staleTime: 10_000,
    }),

  templates: () =>
    queryOptions({
      queryKey: ["resources", "templates"],
      queryFn: () => apiClient.get<TemplateListResponse>("/api/resources/templates"),
      staleTime: 5 * 60 * 1000,
      retry: 1,
    }),

  bgm: () =>
    queryOptions({
      queryKey: ["resources", "bgm"],
      queryFn: () => apiClient.get<BGMListResponse>("/api/resources/bgm"),
      staleTime: 5 * 60 * 1000,
      retry: 1,
    }),

  mediaWorkflows: () =>
    queryOptions({
      queryKey: ["resources", "workflows", "media"],
      queryFn: () => apiClient.get<WorkflowListResponse>("/api/resources/workflows/media"),
      staleTime: 5 * 60 * 1000,
      retry: 1,
    }),

  ttsWorkflows: () =>
    queryOptions({
      queryKey: ["resources", "workflows", "tts"],
      queryFn: () => apiClient.get<WorkflowListResponse>("/api/resources/workflows/tts"),
      staleTime: 5 * 60 * 1000,
      retry: 1,
    }),
};
