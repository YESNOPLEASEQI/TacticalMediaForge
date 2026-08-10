import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderKanban, RefreshCw } from "lucide-react";
import { deleteReferenceAsset, projectQueries, updateProject, uploadReferenceAsset } from "@/api/projects";
import { resourceQueries } from "@/api/resources";
import { OperationsShell, WorkbenchHeader } from "@/components/operations/OperationsShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import type { ReferenceAsset, Task, TaskStatus } from "@/types/api";
import type { SessionDetail } from "@/types/history";
import { LLMModelSummary } from "@/features/settings/LLMModelSummary";
import { ResourceNotice } from "@/features/video/ResourceNotice";
import { ScriptStage, type ScriptGenerationFeedback } from "@/features/video/ScriptStage";
import { StoryboardStage } from "@/features/video/StoryboardStage";
import { VideoStage } from "@/features/video/VideoStage";
import { WorkflowStepNav } from "@/features/video/WorkflowStepNav";
import {
  buildProjectDraftUpdate,
  restoreProjectWorkflow,
} from "@/features/projects/projectModel";
import type { ProjectWorkspace } from "@/types/projects";
import { useGlobalTasks } from "@/features/tasks/GlobalTaskManager";
import { applyProjectJobsToDraft, isActiveJob, taskFromJob, videoJobMatchesDraft } from "@/features/tasks/taskModel";
import { gsap, useGSAP } from "@/lib/gsap";
import {
  buildVideoRequest,
  canEnterStage,
  canGenerateVideo,
  containsCjk,
  createEmptyWorkflow,
  enterStoryboardFromScript,
  hasUnsubmittedChanges,
  loadWorkflowDraft,
  markWorkflowChanged,
  markResearchInputsChanged,
  markWorkflowSubmitted,
  saveWorkflowDraft,
  type EditableStoryboardScene,
  type VideoWorkflowDraft,
  type WorkflowStage,
} from "@/features/video/workflow";

function withTaskSceneStatus(
  scenes: EditableStoryboardScene[],
  status?: string,
  percentage = 0,
) {
  if (!status) return scenes;
  if (status === "completed")
    return scenes.map((scene) => ({ ...scene, status: "completed" as const }));
  if (status === "failed") {
    const active = Math.min(
      scenes.length - 1,
      Math.floor((percentage / 100) * scenes.length),
    );
    return scenes.map((scene, index) => ({
      ...scene,
      status:
        index === active
          ? ("failed" as const)
          : index < active
            ? ("completed" as const)
            : ("queued" as const),
    }));
  }
  if (status === "pending")
    return scenes.map((scene) => ({ ...scene, status: "queued" as const }));
  if (status === "running") {
    const active = Math.min(
      scenes.length - 1,
      Math.floor((percentage / 100) * scenes.length),
    );
    return scenes.map((scene, index) => ({
      ...scene,
      status:
        index < active
          ? ("completed" as const)
          : index === active
            ? ("running" as const)
            : ("queued" as const),
    }));
  }
  return scenes;
}

function taskStatusFromHistory(
  status: SessionDetail["generation_jobs"][number]["status"],
): TaskStatus {
  if (status === "queued") return "pending";
  if (status === "success") return "completed";
  return status;
}

function taskFromHistory(detail?: SessionDetail): Task | undefined {
  const job = detail?.generation_jobs[0];
  if (!job) return undefined;
  const result = job.result;
  return {
    task_id: job.id,
    task_type: "video_generation",
    status: taskStatusFromHistory(job.status),
    progress: {
      current: job.progress,
      total: 100,
      percentage: job.progress,
      message:
        job.status === "success"
          ? "任务已完成"
          : "已恢复项目任务状态",
    },
    result: {
      video_url:
        typeof result.video_url === "string"
          ? result.video_url
          : (detail?.session.video_url ?? undefined),
      duration:
        typeof result.duration === "number"
          ? result.duration
          : (job.duration ?? undefined),
      file_size:
        typeof result.file_size === "number" ? result.file_size : undefined,
    },
    error: job.error_message,
    created_at:
      job.created_at ?? detail?.session.created_at ?? new Date(0).toISOString(),
    started_at: job.created_at,
    completed_at: job.completed_at,
    request_params: job.params,
  };
}

function scriptGenerationErrorMessage(error: string | null) {
  if (!error) return "脚本生成未能完成，请稍后重试。";
  if (
    error === "script_generation_timeout" ||
    error.toLowerCase().includes("timed out") ||
    error.includes("referenced script generation failed after retries")
  ) {
    return "脚本生成超时，模型未在规定时间内返回完整内容。请重试，或切换快速生成。";
  }
  return "脚本生成未能完成，请检查模型连接后重试。";
}

function stringArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function scriptReferenceSources(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return [];
    const source = item as Record<string, unknown>;
    const url = typeof source.url === "string" ? source.url : "";
    if (!url) return [];
    return [{
      title: typeof source.title === "string" && source.title ? source.title : url,
      url,
    }];
  });
}

interface VideoGeneratorPageProps {
  projectId: string;
  onOpenProjects?: () => void;
  onOpenSettings: () => void;
}

export function VideoGeneratorPage({
  projectId,
  onOpenProjects,
  onOpenSettings,
}: VideoGeneratorPageProps) {
  const scopeId = projectId;
  const localDraft = React.useMemo(() => loadWorkflowDraft(scopeId), [scopeId]);
  const [draft, setDraft] = React.useState<VideoWorkflowDraft>(
    () => localDraft ?? createEmptyWorkflow(scopeId),
  );
  const [databaseSaveStatus, setDatabaseSaveStatus] = React.useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");
  const pageRef = React.useRef<HTMLDivElement>(null);
  const stageRef = React.useRef<HTMLDivElement>(null);
  const serverInitialized = React.useRef(!scopeId);
  const projectSnapshotRef = React.useRef<ProjectWorkspace | null>(null);
  const researchDefaultApplied = React.useRef(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const {
    jobsForProject,
    retryResearch,
    startResearch,
    startScript,
    startStoryboard,
    startVideo,
    stop,
  } = useGlobalTasks();
  const { contextSafe } = useGSAP({ scope: pageRef });

  const healthQuery = useQuery(resourceQueries.health());
  const templatesQuery = useQuery({
    ...resourceQueries.templates(),
    enabled: healthQuery.isSuccess,
  });
  const bgmQuery = useQuery({
    ...resourceQueries.bgm(),
    enabled: healthQuery.isSuccess,
  });
  const projectQuery = useQuery(projectQueries.workspace(projectId));
  const referenceAssetsQuery = useQuery(projectQueries.referenceAssets(projectId));
  const uploadReferenceMutation = useMutation({
    mutationFn: (file: File) => uploadReferenceAsset(projectId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", projectId, "reference-assets"] }),
  });
  const deleteReferenceMutation = useMutation({
    mutationFn: (assetId: string) => deleteReferenceAsset(projectId, assetId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", projectId, "reference-assets"] }),
  });
  const projectJobs = jobsForProject(projectId);
  const latestVideoJob = projectJobs.find((job) => videoJobMatchesDraft(job, draft));
  const hasCompletedVideo = latestVideoJob?.status === "completed";

  React.useEffect(() => {
    if (scopeId && !serverInitialized.current) return;
    saveWorkflowDraft(draft);
  }, [draft, scopeId]);

  React.useEffect(() => {
    if (!projectQuery.data) return;
    projectSnapshotRef.current = projectQuery.data;
    if (serverInitialized.current) return;
    setDraft(applyProjectJobsToDraft(restoreProjectWorkflow(projectQuery.data, localDraft), projectJobs));
    serverInitialized.current = true;
  }, [projectQuery.data, localDraft, scopeId]);

  React.useEffect(() => {
    if (
      researchDefaultApplied.current ||
      !healthQuery.data?.research_enabled ||
      !projectQuery.data ||
      localDraft ||
      projectQuery.data.project.settings_json.workspace_draft
    ) return;
    researchDefaultApplied.current = true;
    setDraft((current) => ({
      ...current,
      research: { ...current.research, mode: "verified", status: "reference_unavailable" },
    }));
  }, [healthQuery.data?.research_enabled, localDraft, projectQuery.data]);

  React.useEffect(() => {
    if (!healthQuery.data || healthQuery.data.research_enabled !== false) return;
    setDraft((current) => current.scriptMode === "reference"
      ? { ...current, scriptMode: "quick" }
      : current);
  }, [healthQuery.data]);

  React.useEffect(() => {
    if (!projectId || !serverInitialized.current) return;
    const workspace = projectSnapshotRef.current;
    if (!workspace) return;
    setDatabaseSaveStatus("saving");
    const timeout = window.setTimeout(() => {
      const payload = buildProjectDraftUpdate(workspace.project, draft, undefined, hasCompletedVideo);
      void updateProject(projectId, payload)
        .then((project) => {
          const nextWorkspace = { ...workspace, project };
          projectSnapshotRef.current = nextWorkspace;
          queryClient.setQueryData(
            ["project", projectId],
            nextWorkspace,
          );
          setDatabaseSaveStatus("saved");
        })
        .catch(() => setDatabaseSaveStatus("error"));
    }, 900);
    return () => window.clearTimeout(timeout);
  }, [draft, hasCompletedVideo, projectId, queryClient]);

  const patchDraft = React.useCallback((patch: Partial<VideoWorkflowDraft>) => {
    setDraft((current) => ({ ...current, ...patch }));
  }, []);

  const patchContent = React.useCallback(
    (patch: Partial<VideoWorkflowDraft>) => {
      setDraft((current) => markWorkflowChanged({ ...current, ...patch }));
    },
    [],
  );

  const patchResearchInputs = React.useCallback(
    (patch: Partial<VideoWorkflowDraft>) => {
      setDraft((current) => markResearchInputsChanged({ ...current, ...patch }));
    },
    [],
  );

  const persistDraftNow = React.useCallback(() => {
    saveWorkflowDraft(draft);
    const workspace = projectSnapshotRef.current;
    if (!workspace) return;
    void updateProject(projectId, buildProjectDraftUpdate(workspace.project, draft, undefined, hasCompletedVideo)).then((project) => {
      projectSnapshotRef.current = { ...workspace, project };
    }).catch(() => setDatabaseSaveStatus("error"));
  }, [draft, hasCompletedVideo, projectId]);

  const narrationMutation = useMutation({
    mutationFn: (request: { text: string; n_scenes: number; min_words: number; max_words: number; mode: "reference" | "quick" }) => startScript({ ...request, project_id: projectId }),
    onSuccess: () => toast({ title: "脚本生成已开始", description: "离开当前页面后仍会继续处理。" }),
    onError: (error) =>
      toast({
        title: "脚本生成失败",
        description:
          error instanceof Error ? error.message : "请检查大模型配置。",
        variant: "destructive",
      }),
  });

  const storyboardMutation = useMutation({
    mutationFn: (request: { narrations: string[]; min_words: number; max_words: number }) => startStoryboard({ ...request, project_id: projectId, asset_type: draft.config.mediaWorkflow.toLowerCase().includes("image_") ? "image" : "video" }),
    onSuccess: () => toast({ title: "分镜生成已开始", description: "离开当前页面后仍会继续处理。" }),
    onError: (error) =>
      toast({
        title: "分镜生成失败",
        description:
          error instanceof Error ? error.message : "无法生成视觉提示词。",
        variant: "destructive",
      }),
  });

  const researchMutation = useMutation({
    mutationFn: () => {
      const request = {
        project_id: projectId,
        topic: draft.title.trim() || draft.sourceText.trim(),
        narrations: draft.narrations.map((item) => item.trim()).filter(Boolean),
        asset_type: draft.config.mediaWorkflow.toLowerCase().includes("image_") ? "image" as const : "video" as const,
        mode: "verified" as const,
        script_revision: draft.research.scriptRevision,
      };
      return draft.research.stale && draft.research.activeJobId
        ? retryResearch(draft.research.activeJobId, request)
        : startResearch(request);
    },
    onMutate: () => setDraft((current) => ({
      ...current,
      research: { ...current.research, status: "researching", warnings: [] },
    })),
    onSuccess: () => toast({ title: "联网参考生成已开始", description: "网络不可用时会自动按普通模式生成。" }),
    onError: (error) => {
      setDraft((current) => ({
        ...current,
        research: { ...current.research, status: "reference_unavailable" },
      }));
      toast({ title: "参考任务启动失败", description: error instanceof Error ? error.message : "无法创建联网参考任务。", variant: "destructive" });
    },
  });

  const generateMutation = useMutation({
    mutationFn: startVideo,
    onSuccess: () => {
      setDraft((current) =>
        markWorkflowSubmitted({ ...current, stage: "video" }),
      );
      toast({
        title: "视频任务已启动",
        description: "可在项目中查看生成进度。",
      });
    },
    onError: (error) =>
      toast({
        title: "视频任务启动失败",
        description:
          error instanceof Error ? error.message : "无法创建视频任务。",
        variant: "destructive",
      }),
  });

  const cancelMutation = useMutation({
    mutationFn: stop,
    onSuccess: async () => {
      toast({ title: "任务已取消" });
      await queryClient.invalidateQueries({ queryKey: ["jobs", "global"] });
    },
    onError: (error) =>
      toast({
        title: "取消失败",
        description:
          error instanceof Error ? error.message : "无法取消当前任务。",
        variant: "destructive",
      }),
  });

  React.useEffect(() => {
    if (!serverInitialized.current || !projectJobs.length) return;
    setDraft((current) => applyProjectJobsToDraft(current, projectJobs));
  }, [projectJobs]);

  const activeScriptJob = projectJobs.find((job) => job.job_type === "script_generation" && isActiveJob(job));
  const latestScriptJob = projectJobs.find((job) => job.job_type === "script_generation");
  const currentScriptJob = latestScriptJob &&
    typeof latestScriptJob.params_json.text === "string" &&
    latestScriptJob.params_json.text.trim() === draft.sourceText.trim()
    ? latestScriptJob
    : undefined;
  const scriptGenerationError = currentScriptJob?.status === "failed"
    ? scriptGenerationErrorMessage(currentScriptJob.error_message)
    : undefined;
  const scriptGenerationFeedback = React.useMemo<ScriptGenerationFeedback>(() => {
    const mode = currentScriptJob?.params_json.mode === "reference" ||
      currentScriptJob?.params_json.mode === "quick"
      ? currentScriptJob.params_json.mode
      : draft.scriptMode;
    const rawResearchStatus = currentScriptJob?.result_json.research_status;
    const researchStatus = rawResearchStatus === "reference_ready" ||
      rawResearchStatus === "partial_reference" ||
      rawResearchStatus === "reference_unavailable" ||
      rawResearchStatus === "quick"
      ? rawResearchStatus
      : undefined;
    const jobStatus = currentScriptJob?.status;
    const status = narrationMutation.isPending || jobStatus === "pending" || jobStatus === "running"
      ? "running"
      : jobStatus ?? "idle";
    return {
      status,
      mode,
      researchStatus,
      sources: scriptReferenceSources(currentScriptJob?.result_json.sources),
      warnings: stringArray(currentScriptJob?.result_json.warnings),
    };
  }, [currentScriptJob, draft.scriptMode, narrationMutation.isPending]);
  const activeStoryboardJob = projectJobs.find((job) => job.job_type === "storyboard_generation" && isActiveJob(job));
  const activeResearchJob = projectJobs.find((job) => job.job_type === "research" && isActiveJob(job));
  const hasPersistedVideoJobs = projectJobs.some((job) => job.job_type === "video_generation");
  const task = taskFromJob(latestVideoJob) ?? (
    hasPersistedVideoJobs ? undefined : taskFromHistory(projectQuery.data?.history ?? undefined)
  );
  const isRunning = task?.status === "pending" || task?.status === "running";
  const workflowBusy = isRunning || Boolean(activeResearchJob) || Boolean(activeStoryboardJob);
  const videoReady = canGenerateVideo(draft);
  const hasChinesePrompt = draft.storyboard.some((scene) => containsCjk(scene.mediaPrompt));
  const templates = templatesQuery.data?.templates ?? [];
  const bgmFiles = bgmQuery.data?.bgm_files ?? [];
  const apiAvailable = healthQuery.isSuccess;
  const displayedScenes = React.useMemo(
    () =>
      withTaskSceneStatus(
        draft.storyboard,
        task?.status,
        task?.progress?.percentage,
      ),
    [draft.storyboard, task?.status, task?.progress?.percentage],
  );
  const resourceError =
    templatesQuery.error instanceof Error
      ? templatesQuery.error.message
      : bgmQuery.error instanceof Error
        ? bgmQuery.error.message
        : undefined;

  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add({ reduceMotion: "(prefers-reduced-motion: reduce)", allowMotion: "(prefers-reduced-motion: no-preference)" }, (context) => {
      const reduced = Boolean(context.conditions?.reduceMotion);
      gsap.fromTo(stageRef.current, {
        autoAlpha: 0,
        y: reduced ? 0 : 20,
        scale: reduced ? 1 : 0.992,
        clipPath: reduced ? "inset(0 0 0 0)" : "inset(0 0 10% 0)",
      }, {
        autoAlpha: 1,
        y: 0,
        scale: 1,
        clipPath: "inset(0 0 0 0)",
        duration: reduced ? 0.2 : 0.62,
        ease: "reveal",
        overwrite: "auto",
        clearProps: "transform,opacity,visibility,clipPath",
      });
    });
    return () => media.revert();
  }, { scope: stageRef, dependencies: [draft.stage], revertOnUpdate: true });

  const transitionStage = contextSafe((stage: WorkflowStage, apply: () => void) => {
    if (stage === draft.stage || !stageRef.current) {
      apply();
      return;
    }
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const targetIndex = ["script", "storyboard", "video"].indexOf(stage);
    const timeline = gsap.timeline({ defaults: { overwrite: "auto" } });
    timeline.to(stageRef.current, {
      autoAlpha: 0,
      y: reduced ? 0 : -12,
      scale: reduced ? 1 : 0.994,
      duration: reduced ? 0.14 : 0.28,
      ease: "interface",
    }).to("[data-testid='workflow-progress-line']", {
      scaleX: targetIndex / 2,
      duration: reduced ? 0.12 : 0.44,
      ease: "interface",
    }, ">").fromTo(`[data-workflow-step='${stage}'] .workflow-step__marker`, {
      scale: reduced ? 1 : 0.86,
    }, {
      scale: 1,
      duration: reduced ? 0.12 : 0.38,
      ease: "impact",
    }, ">-0.08").call(apply);
  });

  const changeStage = (stage: WorkflowStage) => {
    if (canEnterStage(draft, stage)) transitionStage(stage, () => patchDraft({ stage }));
  };

  return (
    <OperationsShell>
      <div ref={pageRef}>
      <WorkbenchHeader
        actions={
          <>
            <Button
              onClick={onOpenProjects}
              size="sm"
              type="button"
              variant="secondary"
            >
              <FolderKanban className="h-4 w-4" />
              项目中心
            </Button>
            <Button
              onClick={() => {
                void healthQuery.refetch();
                void templatesQuery.refetch();
                void bgmQuery.refetch();
              }}
              size="sm"
              type="button"
              variant="secondary"
            >
              <RefreshCw className="h-4 w-4" />
              刷新连接
            </Button>
          </>
        }
        meta={
          <>
            {projectId ? (
              <Badge variant={databaseSaveStatus === "error" ? "destructive" : "secondary"}>
                {databaseSaveStatus === "saving"
                  ? "保存中…"
                  : databaseSaveStatus === "error"
                    ? "保存失败"
                    : "已保存"}
              </Badge>
            ) : null}
          </>
        }
        title={projectQuery.data?.project.title || draft.title || "军事科普视频生成"}
      />
      <WorkflowStepNav
        onChange={changeStage}
        scriptConfirmed={draft.scriptConfirmed}
        stage={draft.stage}
        storyboardConfirmed={draft.storyboardConfirmed}
      />

      <div className="mb-4"><LLMModelSummary onOpenSettings={onOpenSettings} /></div>
      <div className="mb-4">
        <ResourceNotice
          apiAvailable={apiAvailable}
          errorMessage={resourceError}
          isLoading={templatesQuery.isLoading || bgmQuery.isLoading}
          templateCount={templates.length}
        />
      </div>

      <div className="workflow-stage-viewport" data-stage={draft.stage} ref={stageRef}>
      {draft.stage === "script" ? (
        <ScriptStage
          bgmFiles={bgmFiles}
          config={draft.config}
          disabled={isRunning}
          isGenerating={narrationMutation.isPending || Boolean(activeScriptJob)}
          generationError={scriptGenerationError}
          generationFeedback={scriptGenerationFeedback}
          narrations={draft.narrations}
          researchCapabilityEnabled={Boolean(healthQuery.data?.research_enabled)}
          scriptMode={draft.scriptMode}
          onConfigChange={(config) => {
            const previousAssetType = draft.config.mediaWorkflow.toLowerCase().includes("image_")
              ? "image"
              : "video";
            const nextAssetType = config.mediaWorkflow.toLowerCase().includes("image_")
              ? "image"
              : "video";
            if (previousAssetType !== nextAssetType) patchResearchInputs({ config });
            else patchContent({ config });
          }}
          onConfirm={() =>
            transitionStage("storyboard", () =>
              setDraft((current) => enterStoryboardFromScript(current)))
          }
          onGenerate={() =>
            (persistDraftNow(), narrationMutation.mutate({
              text: draft.sourceText,
              n_scenes: draft.config.nScenes,
              min_words: 5,
              max_words: 20,
              mode: draft.scriptMode,
            }))
          }
          onScriptModeChange={(scriptMode) => patchContent({ scriptMode })}
          onNarrationsChange={(narrations) =>
            patchResearchInputs({
              narrations,
              scriptConfirmed: false,
              storyboard: [],
              storyboardConfirmed: false,
            })
          }
          onSourceTextChange={(sourceText) => patchResearchInputs({ sourceText })}
          onTitleChange={(title) => patchResearchInputs({ title })}
          sourceText={draft.sourceText}
          templates={templates}
          title={draft.title}
        />
      ) : null}

      {draft.stage === "storyboard" ? (
        <StoryboardStage
          projectId={projectId}
          disabled={workflowBusy}
          isGenerating={storyboardMutation.isPending || researchMutation.isPending || Boolean(activeStoryboardJob) || Boolean(activeResearchJob)}
          onChange={(storyboard) =>
            patchContent({ storyboard, storyboardConfirmed: false })
          }
          onConfirm={() =>
            transitionStage("video", () => patchDraft({ storyboardConfirmed: true, stage: "video" }))
          }
          onGenerate={() => {
            persistDraftNow();
            if (draft.research.mode === "verified") researchMutation.mutate();
            else storyboardMutation.mutate({ narrations: draft.narrations.filter((item) => item.trim()), min_words: 35, max_words: 120 });
          }}
          onModeChange={(mode) => patchDraft({
            research: {
              ...draft.research,
              mode,
              status: mode === "quick" ? "quick" : "reference_unavailable",
              sourceCount: mode === "quick" ? 0 : draft.research.sourceCount,
              sources: mode === "quick" ? [] : draft.research.sources,
              warnings: mode === "quick" ? [] : draft.research.warnings,
            },
            storyboardConfirmed: false,
          })}
          onReferenceModeChange={(referenceMode) => patchContent({
            config: { ...draft.config, referenceMode },
            storyboardConfirmed: false,
          })}
          referenceMode={draft.config.referenceMode ?? "standard"}
          referenceAssets={(referenceAssetsQuery.data ?? []) as ReferenceAsset[]}
          referenceAssetsError={
            uploadReferenceMutation.error instanceof Error
              ? uploadReferenceMutation.error.message
              : deleteReferenceMutation.error instanceof Error
                ? deleteReferenceMutation.error.message
                : undefined
          }
          referenceAssetsLoading={referenceAssetsQuery.isLoading}
          referenceAssetsUploading={uploadReferenceMutation.isPending}
          onDeleteReference={(assetId) => deleteReferenceMutation.mutate(assetId)}
          onUploadReference={(file) => uploadReferenceMutation.mutate(file)}
          research={activeResearchJob
            ? { ...draft.research, status: "researching" }
            : draft.research}
          researchCapabilityEnabled={Boolean(healthQuery.data?.research_enabled)}
          scenes={draft.storyboard}
        />
      ) : null}

      {draft.stage === "video" ? (
        <VideoStage
          canGenerate={videoReady}
          generationBlockReason={!videoReady
            ? hasChinesePrompt
              ? "生成提示词只能使用英文，请先移除中文字符。"
              : "请先确认至少一个包含旁白和提示词的分镜。"
            : undefined}
          hasUnsubmittedChanges={hasUnsubmittedChanges(draft)}
          isCancelling={cancelMutation.isPending}
          isRestoringTask={projectQuery.isPending}
          isSubmitting={generateMutation.isPending}
          onCancel={() => {
            if (task?.task_id) cancelMutation.mutate(task.task_id);
          }}
          onGenerate={() => { persistDraftNow(); generateMutation.mutate(buildVideoRequest(draft)); }}
          scenes={displayedScenes}
          task={task}
        />
      ) : null}
      </div>
      </div>
    </OperationsShell>
  );
}
