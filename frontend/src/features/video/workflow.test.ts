import { describe, expect, it } from "vitest";
import type { SessionDetail } from "@/types/history";
import {
  buildVideoRequest,
  canEnterStage,
  canGenerateVideo,
  containsCjk,
  createEmptyWorkflow,
  createStoryboard,
  enterStoryboardFromScript,
  estimateNarrationDuration,
  hasUnsubmittedChanges,
  markWorkflowChanged,
  markWorkflowSubmitted,
  markResearchInputsChanged,
  normalizeEstimatedDuration,
  mergeWorkflowDraft,
  restoreWorkflowFromHistory,
  type VideoWorkflowDraft,
} from "@/features/video/workflow";

describe("script to storyboard transition", () => {
  it("does not carry script research failure feedback into an unstarted storyboard", () => {
    const draft = createEmptyWorkflow("project-1", true);
    draft.narrations = [" first paragraph ", "", " second paragraph "];
    draft.research = {
      ...draft.research,
      status: "reference_unavailable",
      sourceCount: 1,
      sources: [{ title: "script source", url: "https://example.test/source" }],
      warnings: ["all_crawls_failed"],
    };

    const storyboardDraft = enterStoryboardFromScript(draft);

    expect(storyboardDraft.stage).toBe("storyboard");
    expect(storyboardDraft.scriptConfirmed).toBe(true);
    expect(storyboardDraft.narrations).toEqual(["first paragraph", "second paragraph"]);
    expect(storyboardDraft.research).toMatchObject({
      status: "reference_unavailable",
      sourceCount: 0,
      sources: [],
      warnings: [],
    });
  });
});

const historyDetail: SessionDetail = {
  session: {
    id: "session-1",
    title: "雷达任务",
    project_type: "video_agent",
    status: "success",
    job_count: 1,
    latest_job_id: "job-1",
    video_url: "/api/files/session-1/final.mp4",
    metadata: {},
  },
  messages: [
    {
      id: "user-message",
      session_id: "session-1",
      role: "user",
      content: { text: "旧输入" },
      metadata: {},
    },
    {
      id: "assistant-message",
      session_id: "session-1",
      role: "assistant",
      content: {
        scenes: [
          { index: 0, narration: "第一段", image_prompt: "prompt 1", duration: 3 },
          { index: 1, narration: "第二段", image_prompt: "prompt 2", duration: 4 },
        ],
      },
      metadata: {},
    },
  ],
  generation_jobs: [
    {
      id: "job-1",
      session_id: "session-1",
      status: "success",
      progress: 100,
      provider: "local",
      prompt: "旧输入",
      params: {
        title: "雷达任务",
        frame_template: "1080x1920/video_default.html",
        media_workflow: "selfhost/video_wan2.1_fusionx.json",
        bgm_volume: 0.2,
      },
      result: { video_url: "/api/files/session-1/final.mp4" },
    },
  ],
  assets: [],
  workflow_snapshots: [],
};

function confirmedDraft(): VideoWorkflowDraft {
  return {
    version: 1,
    sessionId: "session-1",
    stage: "storyboard",
    sourceText: "雷达科普",
    title: "雷达任务",
    narrations: ["第一段", "第二段"],
    scriptConfirmed: true,
    scriptMode: "quick",
    storyboard: [
      {
        id: "scene-0",
        index: 0,
        narration: "第一段",
        visualDescription: "雷达阵列",
        mediaPrompt: "edited prompt",
        estimatedDuration: 4,
        assetType: "video",
        status: "draft",
      },
      {
        id: "scene-1",
        index: 1,
        narration: "第二段",
        visualDescription: "指挥中心",
        mediaPrompt: "second prompt",
        estimatedDuration: 5,
        assetType: "video",
        status: "draft",
      },
    ],
    storyboardConfirmed: true,
    research: {
      mode: "quick",
      activeJobId: null,
      inputHash: null,
      scriptRevision: 0,
      status: "quick",
      sourceCount: 0,
      sources: [],
      warnings: [],
      stale: false,
    },
    config: {
      nScenes: 2,
      frameTemplate: "1080x1920/video_default.html",
      mediaWorkflow: "selfhost/video_wan2.1_fusionx.json",
      bgmEnabled: false,
      bgmPath: "",
      bgmVolume: 0.3,
    },
  };
}

describe("video workflow state", () => {
  it("uses LTX 2.3 for new video workflows", () => {
    expect(createEmptyWorkflow().config.mediaWorkflow).toBe("selfhost/video_ltx2_3_t2v.json");
  });

  it("uses whole seconds for storyboard duration estimates", () => {
    expect(estimateNarrationDuration("1234567890")).toBe(3);
    expect(Number.isInteger(estimateNarrationDuration("1234567890"))).toBe(true);
    expect(normalizeEstimatedDuration(4.2)).toBe(5);
  });

  it("tracks edits made after the latest video submission", () => {
    const submitted = markWorkflowSubmitted(confirmedDraft());
    const changed = markWorkflowChanged(submitted);

    expect(hasUnsubmittedChanges(submitted)).toBe(false);
    expect(hasUnsubmittedChanges(changed)).toBe(true);
    expect(markWorkflowSubmitted(changed).submittedRevision).toBe(changed.contentRevision);
  });

  it("keeps script paragraphs as narrations and maps them one-to-one", () => {
    const scenes = createStoryboard(["第一段", "第二段"], ["prompt 1", "prompt 2"]);

    expect(scenes.map((scene) => scene.narration)).toEqual(["第一段", "第二段"]);
    expect(scenes.map((scene) => scene.index)).toEqual([0, 1]);
  });

  it("restores narrations and scenes from history storyboard", () => {
    const restored = restoreWorkflowFromHistory(historyDetail);

    expect(restored.narrations).toEqual(["第一段", "第二段"]);
    expect(restored.storyboard[0].mediaPrompt).toBe("prompt 1");
    expect(restored.stage).toBe("video");
  });

  it("sends the exact confirmed storyboard", () => {
    const draft = confirmedDraft();
    draft.storyboard[0].estimatedDuration = 4.2;
    const request = buildVideoRequest(draft);

    expect(request.confirmed_storyboard?.[0].media_prompt).toBe("edited prompt");
    expect(request.confirmed_storyboard?.[0].visual_description).toBe("edited prompt");
    expect(request.confirmed_storyboard?.[0].estimated_duration).toBe(5);
    expect(request.text).toBe("第一段\n\n第二段");
    expect(request.mode).toBe("fixed");
    expect(request.workflow_revision).toBe(0);
  });

  it("guards later stages until their inputs are confirmed", () => {
    const draft = confirmedDraft();

    expect(canEnterStage({ ...draft, scriptConfirmed: false }, "storyboard")).toBe(false);
    expect(canEnterStage({ ...draft, storyboardConfirmed: false }, "video")).toBe(false);
    expect(canGenerateVideo({ ...draft, storyboardConfirmed: false })).toBe(true);
    expect(canGenerateVideo(draft)).toBe(true);
  });

  it("blocks Chinese generation prompts", () => {
    const draft = confirmedDraft();
    draft.storyboard[0].mediaPrompt = "雷达 cinematic tracking shot";

    expect(containsCjk(draft.storyboard[0].mediaPrompt)).toBe(true);
    expect(canGenerateVideo(draft)).toBe(false);
  });

  it("marks active verified research stale after script inputs change", () => {
    const draft = confirmedDraft();
    draft.research = {
      mode: "verified",
      activeJobId: "research-1",
      inputHash: "hash",
      scriptRevision: 2,
      status: "reference_ready",
      sourceCount: 1,
      sources: [],
      warnings: [],
      stale: false,
    };

    const changed = markResearchInputsChanged(draft);

    expect(changed.research.scriptRevision).toBe(3);
    expect(changed.research.stale).toBe(true);
    expect(changed.storyboardConfirmed).toBe(false);
  });

  it("sends complete verified scene provenance to the backend", () => {
    const draft = confirmedDraft();
    draft.research = {
      mode: "verified",
      activeJobId: "research-1",
      inputHash: "hash",
      scriptRevision: 2,
      status: "reference_ready",
      sourceCount: 1,
      sources: [],
      warnings: [],
      stale: false,
    };
    draft.storyboard[0] = {
      ...draft.storyboard[0],
      researchJobId: "research-1",
      subjectId: "subject-1",
      claimIds: ["claim-1"],
      visualFactIds: ["visual-1"],
      fieldProvenance: {
        subject: { claim_ids: ["claim-1"], visual_fact_ids: ["visual-1"], creative: false },
        environment: { claim_ids: ["claim-1"], visual_fact_ids: [], creative: false },
        opening_state: { claim_ids: ["claim-1"], visual_fact_ids: [], creative: false },
        action: { claim_ids: ["claim-1"], visual_fact_ids: [], creative: false },
        ending_frame: { claim_ids: ["claim-1"], visual_fact_ids: [], creative: false },
      },
      fallbackLevel: "verified_specific",
      verificationStatus: "verified",
      negativeConstraints: ["no logos"],
      warnings: [],
    };
    draft.storyboard[1] = { ...draft.storyboard[0], id: "scene-1", index: 1, narration: draft.narrations[1] };

    const request = buildVideoRequest(draft);

    expect(request.verification_mode).toBe("verified");
    expect(request.script_revision).toBe(2);
    expect(request.confirmed_storyboard?.[0]).toMatchObject({
      research_job_id: "research-1",
      subject_id: "subject-1",
      claim_ids: ["claim-1"],
      visual_fact_ids: ["visual-1"],
      fallback_level: "verified_specific",
      verification_status: "verified",
      negative_constraints: ["no logos"],
    });
  });

  it("allows partial and stale research storyboards once confirmed", () => {
    const draft = confirmedDraft();
    draft.research = {
      mode: "verified",
      activeJobId: "research-1",
      inputHash: "hash",
      scriptRevision: 2,
      status: "reference_unavailable",
      sourceCount: 0,
      sources: [],
      warnings: ["research_search_unavailable"],
      stale: false,
    };

    draft.storyboard = draft.storyboard.map((scene) => ({
      ...scene,
      researchJobId: "research-1",
      fallbackLevel: "generic_safe",
      verificationStatus: "partial",
    }));
    draft.research.status = "partial_reference";

    expect(canGenerateVideo(draft)).toBe(true);
    expect(canGenerateVideo({
      ...draft,
      research: { ...draft.research, status: "reference_ready", stale: true },
    })).toBe(true);
    expect(buildVideoRequest(draft).verification_mode).toBe("unverified");
  });

  it("blocks the old unanchored generic fallback storyboard", () => {
    const draft = confirmedDraft();
    draft.storyboard[0].mediaPrompt = [
      "A restrained wide establishing view introduces a credible military",
      "technology subject in an ordinary operational environment.",
    ].join(" ");

    expect(canGenerateVideo(draft)).toBe(false);
  });

  it("blocks the retired non-identifying template and duplicate prompts", () => {
    const retired = confirmedDraft();
    retired.storyboard[0].mediaPrompt = "A non-identifying main battle tank is at rest with neutral markings.";
    expect(canGenerateVideo(retired)).toBe(false);

    const duplicate = confirmedDraft();
    duplicate.storyboard[1].mediaPrompt = "  EDITED   prompt ";
    expect(canGenerateVideo(duplicate)).toBe(false);
  });

  it("removes empty provenance from the submitted video request", () => {
    const draft = confirmedDraft();
    draft.storyboard[0].fieldProvenance = {
      subject: { claim_ids: [], visual_fact_ids: [], creative: false },
      camera: { claim_ids: [], visual_fact_ids: [], creative: true },
    };

    expect(buildVideoRequest(draft).confirmed_storyboard?.[0].field_provenance).toEqual({
      camera: { claim_ids: [], visual_fact_ids: [], creative: true },
    });
  });

  it("allows a fully sourced low-confidence verified storyboard", () => {
    const draft = confirmedDraft();
    const provenance = {
      subject: { claim_ids: ["claim-1"], visual_fact_ids: ["visual-1"], creative: false },
      environment: { claim_ids: ["claim-1"], visual_fact_ids: [], creative: false },
      opening_state: { claim_ids: ["claim-1"], visual_fact_ids: [], creative: false },
      action: { claim_ids: ["claim-1"], visual_fact_ids: [], creative: false },
      ending_frame: { claim_ids: ["claim-1"], visual_fact_ids: [], creative: false },
    };
    draft.research = {
      mode: "verified",
      activeJobId: "research-1",
      inputHash: "hash",
      scriptRevision: 2,
      status: "reference_ready",
      sourceCount: 1,
      sources: [],
      warnings: [],
      stale: false,
    };
    draft.storyboard = draft.storyboard.map((scene) => ({
      ...scene,
      researchJobId: "research-1",
      claimIds: ["claim-1"],
      visualFactIds: ["visual-1"],
      fieldProvenance: provenance,
      fallbackLevel: "verified_generic",
      verificationStatus: "low_confidence_verified",
      warnings: ["single_source_verification"],
    }));

    expect(canGenerateVideo(draft)).toBe(true);
    expect(buildVideoRequest(draft).confirmed_storyboard?.[0]).toMatchObject({
      verification_status: "low_confidence_verified",
      warnings: ["single_source_verification"],
    });
  });

  it("keeps the server snapshot when a local history draft is empty", () => {
    const server = restoreWorkflowFromHistory(historyDetail);
    const emptyLocal = { ...confirmedDraft(), narrations: [""], storyboard: [], sourceText: "", title: "" };

    expect(mergeWorkflowDraft(server, emptyLocal)).toEqual(server);
  });

  it("overlays a meaningful local edit onto the server snapshot", () => {
    const server = restoreWorkflowFromHistory(historyDetail);
    const local = { ...confirmedDraft(), narrations: ["本地修改段落"], scriptConfirmed: false };

    expect(mergeWorkflowDraft(server, local).narrations).toEqual(["本地修改段落"]);
    expect(mergeWorkflowDraft(server, local).scriptConfirmed).toBe(false);
  });

  it("prefers confirmed storyboard metadata stored in job params", () => {
    const detail: SessionDetail = {
      ...historyDetail,
      generation_jobs: historyDetail.generation_jobs.map((job) => ({
        ...job,
        params: {
          ...job.params,
          confirmed_storyboard: [
            {
              index: 0,
              narration: "第一段",
              visual_description: "用户编辑的画面描述",
              media_prompt: "用户编辑的提示词",
              estimated_duration: 8,
              asset_type: "image",
            },
          ],
        },
      })),
    };

    const restored = restoreWorkflowFromHistory(detail);
    expect(restored.storyboard[0]).toMatchObject({
      visualDescription: "用户编辑的提示词",
      mediaPrompt: "用户编辑的提示词",
      estimatedDuration: 8,
      assetType: "image",
    });
  });
});
