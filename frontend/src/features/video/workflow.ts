import type {
  FallbackLevel,
  FieldProvenance,
  ResearchStatus,
  VerificationStatus,
  VideoGenerateRequest,
} from "@/types/api";
import type { HistoryScene, SessionDetail } from "@/types/history";

export type WorkflowStage = "script" | "storyboard" | "video";
export type StoryboardAssetType = "image" | "video";
export type StoryboardSceneStatus = "draft" | "queued" | "running" | "completed" | "failed";

export interface EditableStoryboardScene {
  id: string;
  index: number;
  narration: string;
  visualDescription: string;
  mediaPrompt: string;
  estimatedDuration: number;
  assetType: StoryboardAssetType;
  status: StoryboardSceneStatus;
  researchJobId?: string | null;
  subjectId?: string | null;
  claimIds?: string[];
  visualFactIds?: string[];
  fieldProvenance?: Record<string, FieldProvenance>;
  fallbackLevel?: FallbackLevel;
  verificationStatus?: VerificationStatus;
  negativeConstraints?: string[];
  warnings?: string[];
  referenceAssetIds?: string[];
  genericFallback?: EditableStoryboardScene | null;
}

export interface WorkflowResearchState {
  mode: "verified" | "quick";
  activeJobId: string | null;
  inputHash: string | null;
  scriptRevision: number;
  status: ResearchStatus;
  sourceCount: number;
  sources: Array<{ title: string; url: string }>;
  warnings: string[];
  stale: boolean;
}

export interface VideoWorkflowConfig {
  nScenes: number;
  frameTemplate: string;
  mediaWorkflow: string;
  bgmEnabled: boolean;
  bgmPath: string;
  bgmVolume: number;
  referenceMode?: "standard" | "h3";
}

export interface VideoWorkflowDraft {
  version: 1;
  promptContractVersion?: "ltx-2.3-creative-v2";
  sessionId: string | null;
  stage: WorkflowStage;
  sourceText: string;
  title: string;
  narrations: string[];
  scriptConfirmed: boolean;
  scriptMode: "reference" | "quick";
  storyboard: EditableStoryboardScene[];
  storyboardConfirmed: boolean;
  config: VideoWorkflowConfig;
  contentRevision?: number;
  submittedRevision?: number;
  appliedJobIds?: string[];
  research: WorkflowResearchState;
}

const defaultMediaWorkflow = "selfhost/video_ltx2_3_t2v.json";
const defaultFrameTemplate = "1080x1920/video_default.html";

function textValue(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function numberValue(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function recordValue(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function containsCjk(value: string) {
  return /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/u.test(value);
}

const retiredStoryboardPhrases = [
  "credible military technology subject",
  "one clearly readable mechanical or human action",
  "functional surfaces, moving parts, and material detail",
  "the subject interacting with its surroundings",
  "settles on a clear operational state",
  "non-identifying",
  "generic non-identifying military environment",
  "subject at rest with neutral markings",
  "non-operational exterior observation",
  "stable full profile with no identifying details",
  "unverified model-specific details",
  "national or unit insignia",
  "weapon loads or internal structures",
  "named operational locations",
] as const;

export function isUnanchoredStoryboardPrompt(value: string) {
  const normalized = value.toLocaleLowerCase().replace(/\s+/gu, " ").trim();
  return retiredStoryboardPhrases.some((phrase) => normalized.includes(phrase));
}

function normalizedPrompt(value: string) {
  return value.toLocaleLowerCase().replace(/\s+/gu, " ").trim();
}

export function hasDuplicateStoryboardPrompts(scenes: EditableStoryboardScene[]) {
  const prompts = scenes.map((scene) => normalizedPrompt(scene.mediaPrompt)).filter(Boolean);
  return new Set(prompts).size !== prompts.length;
}

export function discardRetiredStoryboard(draft: VideoWorkflowDraft): VideoWorkflowDraft {
  if (!draft.storyboard.some((scene) => isUnanchoredStoryboardPrompt(scene.mediaPrompt))) {
    return draft.promptContractVersion === "ltx-2.3-creative-v2"
      ? draft
      : { ...draft, promptContractVersion: "ltx-2.3-creative-v2" };
  }
  return {
    ...draft,
    promptContractVersion: "ltx-2.3-creative-v2",
    stage: draft.scriptConfirmed ? "storyboard" : "script",
    storyboard: [],
    storyboardConfirmed: false,
    contentRevision: (draft.contentRevision ?? 0) + 1,
    research: {
      ...draft.research,
      activeJobId: null,
      status: draft.research.mode === "verified" ? "reference_unavailable" : "quick",
      stale: true,
    },
  };
}

export function createEmptyWorkflow(
  sessionId: string | null = null,
  researchEnabled = false,
): VideoWorkflowDraft {
  return {
    version: 1,
    promptContractVersion: "ltx-2.3-creative-v2",
    sessionId,
    stage: "script",
    sourceText: "",
    title: "",
    narrations: [""],
    scriptConfirmed: false,
    scriptMode: researchEnabled ? "reference" : "quick",
    storyboard: [],
    storyboardConfirmed: false,
    contentRevision: 0,
    submittedRevision: 0,
    research: {
      mode: researchEnabled ? "verified" : "quick",
      activeJobId: null,
      inputHash: null,
      scriptRevision: 0,
      status: researchEnabled ? "reference_unavailable" : "quick",
      sourceCount: 0,
      sources: [],
      warnings: [],
      stale: false,
    },
    config: {
      nScenes: 5,
      frameTemplate: defaultFrameTemplate,
      mediaWorkflow: defaultMediaWorkflow,
      bgmEnabled: false,
      bgmPath: "",
      bgmVolume: 0.3,
      referenceMode: "standard",
    },
  };
}

export function estimateNarrationDuration(narration: string) {
  const characterCount = narration.trim().replace(/\s+/g, "").length;
  return Math.max(2, Math.ceil(characterCount / 4.2));
}

export function normalizeEstimatedDuration(duration: number) {
  return Math.max(1, Math.ceil(Number.isFinite(duration) ? duration : 1));
}

export function markWorkflowChanged(draft: VideoWorkflowDraft): VideoWorkflowDraft {
  return { ...draft, contentRevision: (draft.contentRevision ?? 0) + 1 };
}

export function markResearchInputsChanged(draft: VideoWorkflowDraft): VideoWorkflowDraft {
  const revision = draft.research.scriptRevision + 1;
  return markWorkflowChanged({
    ...draft,
    storyboardConfirmed: false,
    research: {
      ...draft.research,
      scriptRevision: revision,
      stale: Boolean(draft.research.activeJobId),
    },
  });
}

export function enterStoryboardFromScript(draft: VideoWorkflowDraft): VideoWorkflowDraft {
  return {
    ...draft,
    narrations: draft.narrations.map((item) => item.trim()).filter(Boolean),
    scriptConfirmed: true,
    storyboardConfirmed: false,
    stage: "storyboard",
    research: {
      ...draft.research,
      status: draft.research.mode === "verified" ? "reference_unavailable" : "quick",
      sourceCount: 0,
      sources: [],
      warnings: [],
    },
  };
}

export function markWorkflowSubmitted(draft: VideoWorkflowDraft): VideoWorkflowDraft {
  return { ...draft, submittedRevision: draft.contentRevision ?? 0 };
}

export function hasUnsubmittedChanges(draft: VideoWorkflowDraft) {
  return (draft.contentRevision ?? 0) !== (draft.submittedRevision ?? 0);
}

export function createStoryboard(
  narrations: string[],
  prompts: string[],
  assetType: StoryboardAssetType = "video",
): EditableStoryboardScene[] {
  return narrations
    .map((narration) => narration.trim())
    .filter(Boolean)
    .map((narration, index) => {
      const prompt = prompts[index]?.trim() ?? "";
      return {
        id: `scene-${index}`,
        index,
        narration,
        visualDescription: prompt,
        mediaPrompt: prompt,
        estimatedDuration: estimateNarrationDuration(narration),
        assetType,
        status: "draft",
        researchJobId: null,
        subjectId: null,
        claimIds: [],
        visualFactIds: [],
        fieldProvenance: {},
        fallbackLevel: "unverified",
        verificationStatus: "unverified",
        negativeConstraints: [],
        warnings: [],
        referenceAssetIds: [],
      };
    });
}

function historyScenes(detail: SessionDetail): HistoryScene[] {
  const messageScenes = detail.messages
    .filter((message) => message.role === "assistant")
    .flatMap((message) => (Array.isArray(message.content.scenes) ? message.content.scenes : []));
  if (messageScenes.length > 0) {
    return messageScenes;
  }

  for (const snapshot of detail.workflow_snapshots) {
    const ui = recordValue(snapshot.ui_json);
    const storyboard = recordValue(ui.storyboard);
    if (Array.isArray(storyboard.frames)) {
      return storyboard.frames.map((scene) => recordValue(scene) as unknown as HistoryScene);
    }
  }
  return [];
}

function splitLegacyText(text: string) {
  const paragraphs = text.split(/\r?\n+/).map((paragraph) => paragraph.trim()).filter(Boolean);
  return paragraphs.length > 0 ? paragraphs : [""];
}

export function restoreWorkflowFromHistory(detail: SessionDetail): VideoWorkflowDraft {
  const job = detail.generation_jobs[0];
  const params = job?.params ?? {};
  const confirmedScenes = Array.isArray(params.confirmed_storyboard)
    ? params.confirmed_storyboard.map((scene) => recordValue(scene) as unknown as HistoryScene)
    : [];
  const scenes = confirmedScenes.length > 0 ? confirmedScenes : historyScenes(detail);
  const sourceText =
    detail.messages.find((message) => message.role === "user")?.content.text ?? job?.prompt ?? "";
  const narrations = scenes.length > 0
    ? scenes.map((scene) => textValue(scene.narration)).filter(Boolean)
    : splitLegacyText(textValue(sourceText));
  const storyboard = scenes.map((scene, position) => {
    const prompt = textValue(scene.media_prompt, textValue(scene.image_prompt));
    const assetType = scene.asset_type ?? scene.media_type ?? "video";
    return {
      id: `scene-${scene.index ?? position}`,
      index: position,
      narration: textValue(scene.narration),
      visualDescription: prompt,
      mediaPrompt: prompt,
      estimatedDuration: normalizeEstimatedDuration(numberValue(
        scene.estimated_duration ?? scene.duration,
        estimateNarrationDuration(textValue(scene.narration)),
      )),
      assetType,
      status: scene.status ?? (detail.session.status === "success" ? "completed" : "draft"),
      researchJobId: textValue(scene.research_job_id) || null,
      subjectId: textValue(scene.subject_id) || null,
      claimIds: Array.isArray(scene.claim_ids) ? scene.claim_ids.filter((item): item is string => typeof item === "string") : [],
      visualFactIds: Array.isArray(scene.visual_fact_ids) ? scene.visual_fact_ids.filter((item): item is string => typeof item === "string") : [],
      fieldProvenance: recordValue(scene.field_provenance) as Record<string, FieldProvenance>,
      fallbackLevel: scene.fallback_level ?? "unverified",
      verificationStatus: scene.verification_status ?? "unverified",
      negativeConstraints: Array.isArray(scene.negative_constraints) ? scene.negative_constraints.filter((item): item is string => typeof item === "string") : [],
      warnings: Array.isArray(scene.warnings) ? scene.warnings.filter((item): item is string => typeof item === "string") : [],
      referenceAssetIds: Array.isArray(scene.reference_asset_ids)
        ? scene.reference_asset_ids.filter((item): item is string => typeof item === "string")
        : [],
    } satisfies EditableStoryboardScene;
  });
  const hasVideo = Boolean(detail.session.video_url || job?.result?.video_url);
  const isRunning = job?.status === "queued" || job?.status === "running";

  return discardRetiredStoryboard({
    ...createEmptyWorkflow(detail.session.id),
    stage: hasVideo || isRunning ? "video" : storyboard.length > 0 ? "storyboard" : "script",
    sourceText: textValue(sourceText),
    title: textValue(params.title, detail.session.title),
    scriptMode: params.mode === "reference" ? "reference" : "quick",
    narrations,
    scriptConfirmed: storyboard.length > 0,
    storyboard,
    storyboardConfirmed: storyboard.length > 0,
    contentRevision: 0,
    submittedRevision: 0,
    research: {
      mode: params.verification_mode === "verified" ? "verified" : "quick",
      activeJobId: textValue(params.research_job_id) || null,
      inputHash: textValue(params.input_hash) || null,
      scriptRevision: numberValue(params.script_revision, 0),
      status: params.verification_mode === "verified" ? "reference_ready" : "quick",
      sourceCount: 0,
      sources: [],
      warnings: [],
      stale: false,
    },
    config: {
      nScenes: numberValue(params.n_scenes, narrations.length || 5),
      frameTemplate: textValue(params.frame_template, defaultFrameTemplate),
      mediaWorkflow: textValue(params.media_workflow, defaultMediaWorkflow),
      bgmEnabled: Boolean(params.bgm_path),
      bgmPath: textValue(params.bgm_path),
      bgmVolume: numberValue(params.bgm_volume, 0.3),
      referenceMode: params.reference_mode === "h3" ? "h3" : "standard",
    },
  });
}

function hasMeaningfulLocalContent(draft: VideoWorkflowDraft) {
  return Boolean(
    draft.sourceText.trim() ||
    draft.title.trim() ||
    draft.narrations.some((narration) => narration.trim()) ||
    draft.storyboard.length > 0,
  );
}

export function mergeWorkflowDraft(
  serverDraft: VideoWorkflowDraft,
  localDraft: VideoWorkflowDraft | null,
) {
  if (!localDraft || !hasMeaningfulLocalContent(localDraft)) return serverDraft;
  return {
    ...serverDraft,
    ...localDraft,
    sessionId: serverDraft.sessionId,
    config: { ...serverDraft.config, ...localDraft.config },
  };
}

export function canEnterStage(draft: VideoWorkflowDraft, stage: WorkflowStage) {
  if (stage === "script") return true;
  if (stage === "storyboard") return draft.scriptConfirmed;
  return draft.scriptConfirmed && draft.storyboardConfirmed;
}

export function canGenerateVideo(draft: VideoWorkflowDraft) {
  return (
    draft.storyboard.length > 0 &&
    !hasDuplicateStoryboardPrompts(draft.storyboard) &&
    draft.storyboard.every((scene) => (
      (scene.referenceAssetIds?.length ?? 0) <= 4 &&
      scene.narration.trim() &&
      scene.mediaPrompt.trim() &&
      !containsCjk(scene.mediaPrompt) &&
      !isUnanchoredStoryboardPrompt(scene.mediaPrompt)
    ))
  );
}

export function videoGenerationBlockReason(draft: VideoWorkflowDraft) {
  if (draft.storyboard.length === 0) return "请先返回分镜阶段并生成至少一个分镜。";
  if (hasDuplicateStoryboardPrompts(draft.storyboard)) return "部分分镜使用了相同的英文生成提示词，请分别修改后再生成。";
  const missingNarration = draft.storyboard.findIndex((scene) => !scene.narration.trim());
  if (missingNarration >= 0) return `SHOT ${String(missingNarration + 1).padStart(2, "0")} 缺少解说词。`;
  const missingPrompt = draft.storyboard.findIndex((scene) => !scene.mediaPrompt.trim());
  if (missingPrompt >= 0) return `SHOT ${String(missingPrompt + 1).padStart(2, "0")} 缺少英文生成提示词。`;
  const chinesePrompt = draft.storyboard.findIndex((scene) => containsCjk(scene.mediaPrompt));
  if (chinesePrompt >= 0) return `SHOT ${String(chinesePrompt + 1).padStart(2, "0")} 的生成提示词包含中文，请改为英文。`;
  const unanchoredPrompt = draft.storyboard.findIndex((scene) => isUnanchoredStoryboardPrompt(scene.mediaPrompt));
  if (unanchoredPrompt >= 0) return `SHOT ${String(unanchoredPrompt + 1).padStart(2, "0")} 的提示词没有写明具体主体。`;
  const tooManyReferences = draft.storyboard.findIndex((scene) => (scene.referenceAssetIds?.length ?? 0) > 4);
  if (tooManyReferences >= 0) return `SHOT ${String(tooManyReferences + 1).padStart(2, "0")} 绑定了超过 4 张装备视觉参考。`;
  return undefined;
}

export function canUseVerifiedGeneration(draft: VideoWorkflowDraft) {
  const activeResearchId = draft.research.activeJobId;
  return (
    draft.research.mode === "verified" &&
    !draft.research.stale &&
    (draft.research.status === "reference_ready" || draft.research.status === "partial_reference") &&
    Boolean(activeResearchId) &&
    draft.storyboard.length > 0 &&
    draft.storyboard.every((scene) => (
      scene.researchJobId === activeResearchId &&
      (scene.verificationStatus === "verified" || scene.verificationStatus === "low_confidence_verified") &&
      (scene.claimIds?.length ?? 0) > 0
    ))
  );
}

function nonEmptyProvenance(
  provenance: Record<string, FieldProvenance> | undefined,
) {
  return Object.fromEntries(
    Object.entries(provenance ?? {}).filter(([, value]) => (
      value.creative || value.claim_ids.length > 0 || value.visual_fact_ids.length > 0
    )),
  );
}

export function buildVideoRequest(draft: VideoWorkflowDraft): VideoGenerateRequest {
  const narrations = draft.narrations.map((narration) => narration.trim()).filter(Boolean);
  return {
    // Legacy fixed-mode backends split paragraphs on a blank line. The
    // confirmed_storyboard remains authoritative on updated backends.
    text: narrations.join("\n\n"),
    mode: "fixed",
    session_id: draft.sessionId,
    confirmed_storyboard: draft.storyboard.map((scene, index) => ({
      index,
      narration: scene.narration.trim(),
      visual_description: scene.mediaPrompt.trim(),
      media_prompt: scene.mediaPrompt.trim(),
      estimated_duration: normalizeEstimatedDuration(scene.estimatedDuration),
      asset_type: scene.assetType,
      research_job_id: scene.researchJobId ?? null,
      subject_id: scene.subjectId ?? null,
      claim_ids: scene.claimIds ?? [],
      visual_fact_ids: scene.visualFactIds ?? [],
      field_provenance: nonEmptyProvenance(scene.fieldProvenance),
      fallback_level: scene.fallbackLevel ?? "unverified",
      verification_status: scene.verificationStatus ?? "unverified",
      negative_constraints: scene.negativeConstraints ?? [],
      warnings: scene.warnings ?? [],
      reference_asset_ids: scene.referenceAssetIds ?? [],
    })),
    reference_mode: draft.config.referenceMode ?? "standard",
    verification_mode: canUseVerifiedGeneration(draft) ? "verified" : "unverified",
    research_topic: canUseVerifiedGeneration(draft) ? draft.title.trim() || draft.sourceText.trim() : null,
    script_revision: draft.research.scriptRevision,
    workflow_revision: draft.contentRevision ?? 0,
    title: draft.title.trim() || null,
    n_scenes: narrations.length,
    min_narration_words: 5,
    max_narration_words: 20,
    min_image_prompt_words: 30,
    max_image_prompt_words: 60,
    media_workflow: draft.config.referenceMode === "h3" ? null : draft.config.mediaWorkflow,
    video_fps: 30,
    frame_template: draft.config.frameTemplate,
    bgm_path: draft.config.bgmEnabled ? draft.config.bgmPath || null : null,
    bgm_volume: draft.config.bgmVolume,
  };
}

export function workflowStorageKey(sessionId: string | null) {
  return `military-video-gen.workflow.${sessionId ?? "new"}`;
}

export function loadWorkflowDraft(sessionId: string | null): VideoWorkflowDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(workflowStorageKey(sessionId));
    if (!value) return null;
    const parsed = JSON.parse(value) as VideoWorkflowDraft;
    if (parsed.version !== 1) return null;
    const defaults = createEmptyWorkflow(sessionId);
    const parsedConfig = recordValue(parsed.config);
    return {
      ...parsed,
      config: {
        ...defaults.config,
        ...parsedConfig,
        referenceMode: parsedConfig.referenceMode === "h3" ? "h3" : "standard",
      },
      storyboard: (Array.isArray(parsed.storyboard) ? parsed.storyboard : []).map((scene) => ({
        ...scene,
        referenceAssetIds: Array.isArray(scene.referenceAssetIds)
          ? scene.referenceAssetIds.filter((item): item is string => typeof item === "string")
          : [],
      })),
      contentRevision: parsed.contentRevision ?? 0,
      submittedRevision: parsed.submittedRevision ?? 0,
      scriptMode: parsed.scriptMode ?? defaults.scriptMode,
      research: {
        ...defaults.research,
        ...parsed.research,
        status: parsed.research?.status ?? (
          parsed.research?.mode === "verified" ? "reference_unavailable" : "quick"
        ),
        sourceCount: parsed.research?.sourceCount ?? 0,
        sources: parsed.research?.sources ?? [],
        warnings: parsed.research?.warnings ?? [],
      },
    };
  } catch {
    return null;
  }
}

export function saveWorkflowDraft(draft: VideoWorkflowDraft) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(workflowStorageKey(draft.sessionId), JSON.stringify(draft));
}
