import { queryOptions } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { Task, VideoGenerateAsyncResponse, VideoGenerateRequest } from "@/types/api";

export function generateVideo(request: VideoGenerateRequest) {
  return apiClient.post<VideoGenerateAsyncResponse, VideoGenerateRequest>(
    "/api/video/generate/async",
    request,
  );
}

export function cancelTask(taskId: string) {
  return apiClient.delete<{ success: boolean; message: string }>(`/api/tasks/${taskId}`);
}

export const videoQueries = {
  list: () =>
    queryOptions({
      queryKey: ["tasks"],
      queryFn: () => apiClient.get<Task[]>("/api/tasks?limit=20"),
      staleTime: 5_000,
    }),

  task: (taskId: string | null) =>
    queryOptions({
      queryKey: ["tasks", taskId],
      queryFn: () => apiClient.get<Task>(`/api/tasks/${taskId}`),
      enabled: Boolean(taskId),
      refetchInterval: (query) => {
        const task = query.state.data as Task | undefined;
        if (!task) {
          return 2_000;
        }

        return task.status === "pending" || task.status === "running" ? 2_000 : false;
      },
      staleTime: 0,
    }),
};
