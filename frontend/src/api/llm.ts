import { queryOptions } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type {
  LLMConfigResponse,
  LLMConfigUpdateRequest,
  LLMModelsRequest,
  LLMModelsResponse,
} from "@/types/api";

export const llmQueries = {
  config: () =>
    queryOptions({
      queryKey: ["llm", "config"],
      queryFn: () => apiClient.get<LLMConfigResponse>("/api/llm/config"),
      staleTime: 15_000,
      retry: 1,
    }),
};

export function saveLLMConfig(request: LLMConfigUpdateRequest) {
  return apiClient.put<LLMConfigResponse, LLMConfigUpdateRequest>("/api/llm/config", request);
}

export function fetchLLMModels(request: LLMModelsRequest) {
  return apiClient.post<LLMModelsResponse, LLMModelsRequest>("/api/llm/models", request);
}
