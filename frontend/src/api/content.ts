import { apiClient } from "@/api/client";

interface NarrationGenerateRequest {
  text: string;
  n_scenes: number;
  min_words: number;
  max_words: number;
}

interface NarrationGenerateResponse {
  success: boolean;
  message: string;
  narrations: string[];
}

interface ImagePromptGenerateRequest {
  narrations: string[];
  min_words: number;
  max_words: number;
}

interface ImagePromptGenerateResponse {
  success: boolean;
  message: string;
  image_prompts: string[];
}

export function generateNarrations(request: NarrationGenerateRequest) {
  return apiClient.post<NarrationGenerateResponse, NarrationGenerateRequest>("/api/content/narration", request);
}

export function generateImagePrompts(request: ImagePromptGenerateRequest) {
  return apiClient.post<ImagePromptGenerateResponse, ImagePromptGenerateRequest>("/api/content/image-prompt", request);
}
