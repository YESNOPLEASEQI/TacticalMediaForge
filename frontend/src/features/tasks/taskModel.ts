import type { Task } from "@/types/api";
import type { GlobalJob } from "@/types/jobs";
import type { FieldProvenance, ResearchStatus } from "@/types/api";
import {
  buildVideoRequest,
  createStoryboard,
  discardRetiredStoryboard,
  estimateNarrationDuration,
  isUnanchoredStoryboardPrompt,
  markResearchInputsChanged,
  type EditableStoryboardScene,
  type VideoWorkflowDraft,
} from "@/features/video/workflow";

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function provenanceFromScene(scene: Record<string, unknown>): Record<string, FieldProvenance> {
  const result: Record<string, FieldProvenance> = {};
  for (const fieldName of [
    "subject", "environment", "opening_state", "action",
    "camera", "composition", "lighting", "ending_frame",
  ]) {
    const field = record(scene[fieldName]);
    const provenance = record(field.provenance);
    const claimIds = strings(provenance.claim_ids);
    const visualFactIds = strings(provenance.visual_fact_ids);
    const creative = provenance.creative === true || field.creative === true;
    if (claimIds.length || visualFactIds.length || creative) {
      result[fieldName] = {
        claim_ids: claimIds,
        visual_fact_ids: visualFactIds,
        creative,
      };
    }
  }
  return result;
}

function researchScene(value: unknown, jobId: string, position: number): EditableStoryboardScene {
  const scene = record(value);
  const narration = text(scene.narration);
  const persistedDuration = typeof scene.estimated_duration === "number"
    ? scene.estimated_duration
    : 0;
  const index = typeof scene.scene_index === "number"
    ? Math.max(0, scene.scene_index - 1)
    : position;
  return {
    id: `scene-${index}`,
    index,
    narration,
    visualDescription: text(scene.visual_description),
    mediaPrompt: text(scene.media_prompt),
    estimatedDuration: persistedDuration > 1
      ? Math.ceil(persistedDuration)
      : estimateNarrationDuration(narration),
    assetType: scene.asset_type === "image" ? "image" : "video",
    status: "draft",
    researchJobId: jobId,
    subjectId: text(scene.subject_id) || null,
    claimIds: strings(scene.claim_ids),
    visualFactIds: strings(scene.visual_fact_ids),
    fieldProvenance: provenanceFromScene(scene),
    fallbackLevel: scene.fallback_level === "verified_specific" ||
      scene.fallback_level === "verified_generic" ||
      scene.fallback_level === "generic_safe" ||
      scene.fallback_level === "insufficient_evidence"
      ? scene.fallback_level
      : "unverified",
    verificationStatus: scene.verification_status === "verified" ||
      scene.verification_status === "low_confidence_verified" ||
      scene.verification_status === "partial" ||
      scene.verification_status === "insufficient_evidence"
      ? scene.verification_status
      : "unverified",
    negativeConstraints: strings(scene.negative_constraints),
    warnings: strings(scene.warnings),
    referenceAssetIds: strings(scene.reference_asset_ids),
    genericFallback: scene.generic_fallback
      ? researchScene(scene.generic_fallback, jobId, position)
      : null,
  };
}

function videoUrlFromResult(result: Record<string, unknown>): string | undefined {
  if (typeof result.video_url === "string" && result.video_url) return result.video_url;
  if (typeof result.video_path !== "string" || !result.video_path) return undefined;

  const parts = result.video_path.replace(/\\/g, "/").split("/").filter(Boolean);
  const outputIndex = parts.lastIndexOf("output");
  const relativeParts = outputIndex >= 0 ? parts.slice(outputIndex + 1) : parts.slice(-1);
  return `/api/files/${relativeParts.map(encodeURIComponent).join("/")}`;
}

export function isActiveJob(job: GlobalJob) {
  return job.status === "pending" || job.status === "running";
}

export function videoJobMatchesDraft(job: GlobalJob, draft: VideoWorkflowDraft) {
  if (job.job_type !== "video_generation" || job.project_id !== draft.sessionId) return false;
  const revision = job.params_json.workflow_revision;
  if (typeof revision === "number") return revision === (draft.contentRevision ?? 0);

  // Legacy jobs predate explicit revision binding. Only accept one when the
  // draft is itself legacy/unchanged and its authoritative request still
  // matches the stored storyboard and rendering configuration.
  if ((draft.contentRevision ?? 0) !== 0 || (draft.submittedRevision ?? 0) !== 0) return false;
  const expected = buildVideoRequest(draft);
  const actualScenes = Array.isArray(job.params_json.confirmed_storyboard)
    ? job.params_json.confirmed_storyboard
    : [];
  return (
    actualScenes.length === (expected.confirmed_storyboard?.length ?? 0) &&
    job.params_json.media_workflow === expected.media_workflow &&
    job.params_json.frame_template === expected.frame_template
  );
}

export function applyProjectJobsToDraft(draft: VideoWorkflowDraft, jobs: GlobalJob[]): VideoWorkflowDraft {
  const applied = new Set(draft.appliedJobIds ?? []);
  let next = discardRetiredStoryboard(draft);
  const completed = jobs
    .filter((job) => job.project_id === draft.sessionId && job.status === "completed" && !applied.has(job.id))
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  for (const job of completed) {
    if (job.job_type === "script_generation") {
      const narrations = strings(job.result_json.narrations);
      if (narrations.length) {
        const scriptMode = job.params_json.mode === "reference" ? "reference" : "quick";
        const resultStatus = text(job.result_json.research_status);
        const researchStatus: ResearchStatus = resultStatus === "reference_ready" ||
          resultStatus === "partial_reference" ||
          resultStatus === "reference_unavailable"
          ? resultStatus
          : scriptMode === "reference" ? "reference_unavailable" : "quick";
        const sourceValues = Array.isArray(job.result_json.sources) ? job.result_json.sources : [];
        const sources = sourceValues.flatMap((value) => {
          const source = record(value);
          const url = text(source.url);
          return url ? [{ title: text(source.title, url), url }] : [];
        });
        next = markResearchInputsChanged({
          ...next,
          narrations,
          scriptConfirmed: false,
          scriptMode,
          storyboard: [],
          storyboardConfirmed: false,
          stage: "script",
          research: {
            ...next.research,
            mode: scriptMode === "reference" ? "verified" : "quick",
            status: researchStatus,
            sourceCount: sources.length,
            sources,
            warnings: strings(job.result_json.warnings),
          },
        });
      }
    }
    if (job.job_type === "storyboard_generation") {
      const prompts = strings(job.result_json.image_prompts);
      const narrations = strings(job.params_json.narrations);
      const assetType = job.params_json.asset_type === "image" ? "image" : "video";
      if (prompts.length && !prompts.some(isUnanchoredStoryboardPrompt)) {
        next = {
          ...next,
          storyboard: createStoryboard(narrations.length ? narrations : next.narrations, prompts, assetType),
          scriptConfirmed: true,
          storyboardConfirmed: false,
          stage: "storyboard",
          research: {
            ...next.research,
            mode: "quick",
            status: "quick",
            sourceCount: 0,
            sources: [],
            warnings: [],
          },
        };
      }
    }
    if (job.job_type === "research") {
      const plan = Array.isArray(job.result_json.storyboard_plan)
        ? job.result_json.storyboard_plan
        : [];
      const researchStatus = (
        job.result_json.research_status === "reference_ready" ||
        job.result_json.research_status === "partial_reference" ||
        job.result_json.research_status === "reference_unavailable"
      ) ? job.result_json.research_status as ResearchStatus : "reference_unavailable";
      const sources = Array.isArray(job.result_json.sources) ? job.result_json.sources : [];
      const referenceSources = sources.flatMap((value) => {
        const source = record(value);
        const url = text(source.url);
        if (!url) return [];
        return [{ title: text(source.title, url), url }];
      });
      const warnings = strings(job.result_json.warnings);
      const plannedScenes = plan.map((scene, index) => researchScene(scene, job.id, index));
      const retiredPlan = plannedScenes.some((scene) => (
        !scene.mediaPrompt.trim() || isUnanchoredStoryboardPrompt(scene.mediaPrompt)
      ));
      next = {
        ...next,
        narrations: plannedScenes.length
          ? plannedScenes.map((scene) => scene.narration).filter(Boolean)
          : next.narrations,
        storyboard: retiredPlan ? [] : plannedScenes,
        scriptConfirmed: true,
        storyboardConfirmed: false,
        stage: "storyboard",
        research: {
          mode: "verified",
          activeJobId: retiredPlan ? null : job.id,
          inputHash: text(job.result_json.input_hash) || null,
          scriptRevision: typeof job.result_json.script_revision === "number"
            ? job.result_json.script_revision
            : next.research.scriptRevision,
          status: retiredPlan ? "reference_unavailable" : researchStatus,
          sourceCount: sources.length,
          sources: referenceSources,
          warnings,
          stale: retiredPlan,
        },
      };
    }
    if (job.job_type === "video_generation") {
      next = {
        ...next,
        scriptConfirmed: true,
        storyboardConfirmed: next.storyboard.length > 0,
      };
    }
    applied.add(job.id);
  }
  return completed.length ? { ...next, appliedJobIds: [...applied] } : draft;
}

export function taskFromJob(job: GlobalJob | undefined): Task | undefined {
  if (!job) return undefined;
  const videoUrl = videoUrlFromResult(job.result_json);
  return {
    task_id: job.id,
    task_type: job.job_type,
    status: job.status,
    progress: {
      current: job.progress,
      total: 100,
      percentage: job.progress,
      message: job.progress_message ?? (job.status === "running" ? "后台生成中" : "任务状态已同步"),
      stage: job.progress_stage,
      current_scene: job.progress_current_scene,
      total_scenes: job.progress_total_scenes,
    },
    result: videoUrl ? { ...job.result_json, video_url: videoUrl } : job.result_json,
    error: job.error_message ?? undefined,
    created_at: job.created_at,
    started_at: job.started_at ?? undefined,
    completed_at: job.completed_at ?? undefined,
    request_params: job.params_json,
  };
}
