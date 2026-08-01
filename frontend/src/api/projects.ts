import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiClient } from "@/api/client";
import { buildProjectCards, projectSessionId } from "@/features/projects/projectModel";
import type { SessionDetail, SessionListResponse } from "@/types/history";
import type {
  Project,
  ProjectCardData,
  ProjectCreate,
  ProjectUpdate,
  ProjectWorkspace,
} from "@/types/projects";

export function createProject(payload: ProjectCreate) {
  return apiClient.post<Project, ProjectCreate>("/api/projects", payload);
}

export function updateProject(projectId: string, payload: ProjectUpdate) {
  return apiClient.patch<Project, ProjectUpdate>(
    `/api/projects/${encodeURIComponent(projectId)}`,
    payload,
  );
}

export function deleteProject(projectId: string) {
  return apiClient.delete<void>(`/api/projects/${encodeURIComponent(projectId)}`);
}

export function getProject(projectId: string) {
  return apiClient.get<Project>(`/api/projects/${encodeURIComponent(projectId)}`);
}

async function compatibleSessions(): Promise<SessionListResponse> {
  try {
    return await apiClient.get<SessionListResponse>("/api/sessions?limit=200");
  } catch (error) {
    console.warn("Project history enrichment is unavailable", error);
    return { sessions: [], total: 0 };
  }
}

export async function getProjectCards(): Promise<ProjectCardData[]> {
  const [projects, history] = await Promise.all([
    apiClient.get<Project[]>("/api/projects?limit=200"),
    compatibleSessions(),
  ]);
  return buildProjectCards(projects, history.sessions);
}

export async function getProjectWorkspace(projectId: string): Promise<ProjectWorkspace> {
  const project = await getProject(projectId);
  try {
    const history = await apiClient.get<SessionDetail>(
      `/api/sessions/${encodeURIComponent(projectSessionId(project))}`,
    );
    return { project, history };
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 404)) {
      console.warn(`Compatible history is unavailable for project ${projectId}`, error);
    }
    return { project, history: null };
  }
}

export const projectQueries = {
  all: () =>
    queryOptions({
      queryKey: ["projects"],
      queryFn: getProjectCards,
      staleTime: 10_000,
    }),
  workspace: (projectId: string | null) =>
    queryOptions({
      queryKey: ["project", projectId],
      queryFn: () => getProjectWorkspace(projectId as string),
      enabled: Boolean(projectId),
      staleTime: 5_000,
    }),
};
