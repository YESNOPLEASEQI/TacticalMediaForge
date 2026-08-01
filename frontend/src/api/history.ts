import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiClient } from "@/api/client";
import type { Task } from "@/types/api";
import type {
  HistoryStatus,
  RetryJobResponse,
  SessionDetail,
  SessionListResponse,
  SessionSummary,
} from "@/types/history";

interface SessionQueryParams {
  status?: HistoryStatus | "all";
  limit?: number;
}

function sessionQueryString(params: SessionQueryParams = {}) {
  const searchParams = new URLSearchParams();

  if (params.status && params.status !== "all") {
    searchParams.set("status", params.status);
  }

  if (params.limit) {
    searchParams.set("limit", String(params.limit));
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function normalizeTaskStatus(status: Task["status"]): HistoryStatus {
  if (status === "pending") {
    return "queued";
  }
  if (status === "completed") {
    return "success";
  }
  return status;
}

function stringParam(params: Record<string, unknown> | null | undefined, key: string) {
  const value = params?.[key];
  return typeof value === "string" ? value : undefined;
}

function numberParam(params: Record<string, unknown> | null | undefined, key: string) {
  const value = params?.[key];
  return typeof value === "number" ? value : undefined;
}

function fallbackTitle(task: Task) {
  const title = stringParam(task.request_params, "title");
  if (title?.trim()) {
    return title;
  }

  const text = stringParam(task.request_params, "text");
  if (text?.trim()) {
    return text.slice(0, 30) + (text.length > 30 ? "..." : "");
  }

  return `生成任务 ${task.task_id.slice(0, 8)}`;
}

function filenameFromUrl(url?: string | null) {
  if (!url) {
    return undefined;
  }

  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.pathname.split("/").filter(Boolean).at(-1);
  } catch {
    return url.split("/").filter(Boolean).at(-1);
  }
}

function taskToSession(task: Task): SessionSummary {
  const params = task.request_params ?? {};

  return {
    id: task.task_id,
    title: fallbackTitle(task),
    project_type: "video_agent",
    status: normalizeTaskStatus(task.status),
    job_count: 1,
    latest_job_id: task.task_id,
    video_url: task.result?.video_url ?? null,
    created_at: task.created_at,
    updated_at: task.completed_at ?? task.started_at ?? task.created_at,
    metadata: {
      task_id: task.task_id,
      duration: task.result?.duration ?? 0,
      file_size: task.result?.file_size ?? 0,
      mode: params.mode,
      n_frames: params.n_scenes ?? 0,
      source: "tasks_fallback",
    },
  };
}

function taskProgress(task: Task) {
  if (task.status === "completed") {
    return 100;
  }

  return Math.max(0, Math.min(100, Math.round(task.progress?.percentage ?? 0)));
}

function taskToSessionDetail(task: Task): SessionDetail {
  const params = task.request_params ?? {};
  const session = taskToSession(task);
  const messageId = `${task.task_id}:user`;
  const prompt = stringParam(params, "text") ?? "";
  const workflowId = stringParam(params, "media_workflow") ?? stringParam(params, "workflow_id") ?? null;
  const videoUrl = task.result?.video_url ?? null;
  const result: Record<string, unknown> = {
    ...(task.result ?? {}),
    video_url: videoUrl,
  };

  return {
    session,
    messages: [
      {
        id: messageId,
        session_id: task.task_id,
        role: "user",
        content: {
          text: prompt,
          attachments: [],
          intent: "generate_video",
        },
        created_at: task.created_at,
        metadata: {
          mode: params.mode,
          title: params.title,
          source: "tasks_fallback",
        },
      },
      {
        id: `${task.task_id}:assistant`,
        session_id: task.task_id,
        role: "assistant",
        content: {
          text:
            task.status === "completed"
              ? "任务已完成，可在右侧查看视频和参数。"
              : task.progress?.message ?? "任务状态已记录。",
          agentSummary: fallbackTitle(task),
          scenes: [],
        },
        created_at: task.completed_at ?? task.started_at ?? task.created_at,
        metadata: {
          source: "tasks_fallback",
        },
      },
    ],
    generation_jobs: [
      {
        id: task.task_id,
        session_id: task.task_id,
        message_id: messageId,
        status: normalizeTaskStatus(task.status),
        progress: taskProgress(task),
        provider: workflowId?.includes("runninghub") ? "runninghub" : "local",
        external_job_id: null,
        prompt,
        negative_prompt: stringParam(params, "negative_prompt") ?? null,
        model_name: null,
        workflow_id: workflowId,
        width: numberParam(params, "media_width") ?? null,
        height: numberParam(params, "media_height") ?? null,
        duration: task.result?.duration ?? null,
        fps: numberParam(params, "video_fps") ?? null,
        seed: numberParam(params, "seed") ?? null,
        error_message: task.error ?? null,
        created_at: task.created_at,
        updated_at: task.completed_at ?? task.started_at ?? task.created_at,
        completed_at: task.completed_at ?? null,
        params,
        result,
      },
    ],
    assets: videoUrl
      ? [
          {
            id: `${task.task_id}:video`,
            job_id: task.task_id,
            session_id: task.task_id,
            asset_type: "video",
            url: videoUrl,
            local_path: null,
            thumbnail_url: null,
            filename: filenameFromUrl(videoUrl) ?? "final.mp4",
            mime_type: "video/mp4",
            size_bytes: task.result?.file_size ?? null,
            duration: task.result?.duration ?? null,
            created_at: task.completed_at ?? task.created_at,
            metadata: {
              source: "tasks_fallback",
            },
          },
        ]
      : [],
    workflow_snapshots: [
      {
        id: `${task.task_id}:workflow`,
        job_id: task.task_id,
        session_id: task.task_id,
        workflow_name: workflowId ?? "未记录工作流",
        workflow_json: {},
        ui_json: {
          input: params,
          task,
        },
        created_at: task.created_at,
      },
    ],
  };
}

async function getSessions(params: SessionQueryParams): Promise<SessionListResponse> {
  try {
    return await apiClient.get<SessionListResponse>(`/api/sessions${sessionQueryString(params)}`);
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error;
    }

    try {
      const tasks = await apiClient.get<Task[]>(`/api/tasks?limit=${params.limit ?? 80}`);
      const sessions = tasks
        .map(taskToSession)
        .filter((session) => !params.status || params.status === "all" || session.status === params.status);
      return { sessions, total: sessions.length };
    } catch (fallbackError) {
      if (fallbackError instanceof ApiError && fallbackError.status === 404) {
        return { sessions: [], total: 0 };
      }
      throw fallbackError;
    }
  }
}

async function getSessionDetail(sessionId: string): Promise<SessionDetail> {
  try {
    return await apiClient.get<SessionDetail>(`/api/sessions/${sessionId}`);
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error;
    }

    const task = await apiClient.get<Task>(`/api/tasks/${sessionId}`);
    return taskToSessionDetail(task);
  }
}

export function retryGenerationJob(jobId: string) {
  return apiClient.post<RetryJobResponse, Record<string, never>>(
    `/api/generation-jobs/${jobId}/retry`,
    {},
  );
}

export function deleteSession(sessionId: string) {
  return apiClient.delete<{ success: boolean; message: string }>(`/api/sessions/${sessionId}`);
}

export const historyQueries = {
  sessions: (params: SessionQueryParams = {}) =>
    queryOptions({
      queryKey: ["history", "sessions", params],
      queryFn: () => getSessions(params),
      staleTime: 10_000,
    }),

  session: (sessionId: string | null) =>
    queryOptions({
      queryKey: ["history", "sessions", sessionId],
      queryFn: () => getSessionDetail(sessionId as string),
      enabled: Boolean(sessionId),
      refetchInterval: (query) => {
        const detail = query.state.data as SessionDetail | undefined;
        const hasRunningJob = detail?.generation_jobs.some(
          (job) => job.status === "queued" || job.status === "running",
        );
        return hasRunningJob ? 2_000 : false;
      },
      staleTime: 5_000,
    }),
};
