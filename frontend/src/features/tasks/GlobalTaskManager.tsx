import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { jobQueries, startScriptJob, startStoryboardJob, startVideoJob, stopJob, type ScriptJobRequest, type StoryboardJobRequest } from "@/api/jobs";
import type { VideoGenerateRequest } from "@/types/api";
import type { GlobalJob } from "@/types/jobs";
import {
  retryResearchJob,
  startResearchJob,
  type ResearchJobRequest,
} from "@/api/research";

interface GlobalTaskContextValue {
  jobs: GlobalJob[];
  jobsForProject: (projectId: string) => GlobalJob[];
  startScript: (request: ScriptJobRequest) => Promise<string>;
  startStoryboard: (request: StoryboardJobRequest) => Promise<string>;
  startVideo: (request: VideoGenerateRequest) => Promise<string>;
  startResearch: (request: ResearchJobRequest) => Promise<string>;
  retryResearch: (jobId: string, request?: ResearchJobRequest) => Promise<string>;
  stop: (jobId: string) => Promise<void>;
}

const GlobalTaskContext = React.createContext<GlobalTaskContextValue | null>(null);

export function GlobalTaskManager({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const jobsQuery = useQuery(jobQueries.global());
  const jobs = jobsQuery.data ?? [];
  const previousStatuses = React.useRef(new Map<string, string>());

  React.useEffect(() => {
    const projectIds = new Set(jobs.map((job) => job.project_id));
    for (const projectId of projectIds) {
      queryClient.setQueryData(["jobs", projectId], jobs.filter((job) => job.project_id === projectId));
    }
    for (const job of jobs) {
      const previous = previousStatuses.current.get(job.id);
      if (previous && previous !== job.status && !["pending", "running"].includes(job.status)) {
        void queryClient.invalidateQueries({ queryKey: ["project", job.project_id] });
        void queryClient.invalidateQueries({ queryKey: ["projects"] });
      }
      previousStatuses.current.set(job.id, job.status);
    }
  }, [jobs, queryClient]);

  const refresh = React.useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["jobs", "global"] });
  }, [queryClient]);

  const value = React.useMemo<GlobalTaskContextValue>(() => ({
    jobs,
    jobsForProject: (projectId) => jobs.filter((job) => job.project_id === projectId),
    startScript: async (request) => { const result = await startScriptJob(request); await refresh(); return result.job_id; },
    startStoryboard: async (request) => { const result = await startStoryboardJob(request); await refresh(); return result.job_id; },
    startVideo: async (request) => { const result = await startVideoJob(request); await refresh(); return result.job_id; },
    startResearch: async (request) => { const result = await startResearchJob(request); await refresh(); return result.job_id; },
    retryResearch: async (jobId, request) => { const result = await retryResearchJob(jobId, request); await refresh(); return result.job_id; },
    stop: async (jobId) => { await stopJob(jobId); await refresh(); },
  }), [jobs, refresh]);

  return <GlobalTaskContext.Provider value={value}>{children}</GlobalTaskContext.Provider>;
}

export function useGlobalTasks() {
  const context = React.useContext(GlobalTaskContext);
  if (!context) throw new Error("useGlobalTasks must be used inside GlobalTaskManager");
  return context;
}

export function useGlobalTasksOptional() {
  return React.useContext(GlobalTaskContext);
}
