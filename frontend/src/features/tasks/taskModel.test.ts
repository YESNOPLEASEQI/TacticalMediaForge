import { describe, expect, it } from "vitest";
import { applyProjectJobsToDraft, taskFromJob, videoJobMatchesDraft } from "@/features/tasks/taskModel";
import { createEmptyWorkflow } from "@/features/video/workflow";
import type { GlobalJob } from "@/types/jobs";

function job(overrides: Partial<GlobalJob>): GlobalJob {
  return {
    id: "job-1",
    project_id: "project-a",
    job_type: "script_generation",
    provider: "local",
    status: "completed",
    progress: 100,
    external_job_id: "job-1",
    params_json: {},
    result_json: {},
    error_message: null,
    created_at: "2026-07-14T00:00:00Z",
    started_at: null,
    completed_at: null,
    ...overrides,
  };
}

describe("project task result restoration", () => {
  it("exposes a persisted video_path as a playable video URL", () => {
    const task = taskFromJob(job({
      job_type: "video_generation",
      result_json: {
        video_path: "C:\\workspace\\output\\20260714_210046_bf60\\final.mp4",
        duration: 12,
      },
    }));

    expect(task?.result?.video_url).toBe("/api/files/20260714_210046_bf60/final.mp4");
  });

  it("does not attach an old video job to a modified storyboard revision", () => {
    const draft = { ...createEmptyWorkflow("project-a"), contentRevision: 7, submittedRevision: 2 };
    const oldVideo = job({
      job_type: "video_generation",
      params_json: { workflow_revision: 2 },
      result_json: { video_url: "/old.mp4" },
    });
    const currentVideo = job({
      id: "video-current",
      job_type: "video_generation",
      params_json: { workflow_revision: 7 },
      result_json: { video_url: "/current.mp4" },
    });

    expect(videoJobMatchesDraft(oldVideo, draft)).toBe(false);
    expect(videoJobMatchesDraft(currentVideo, draft)).toBe(true);
  });

  it("restores completed script and storyboard jobs for the same project", () => {
    const draft = createEmptyWorkflow("project-a");
    const restored = applyProjectJobsToDraft(draft, [
      job({ result_json: { narrations: ["第一段", "第二段"] } }),
      job({
        id: "job-2",
        job_type: "storyboard_generation",
        params_json: { narrations: ["第一段", "第二段"], asset_type: "video" },
        result_json: { image_prompts: ["画面一", "画面二"] },
      }),
    ]);

    expect(restored.narrations).toEqual(["第一段", "第二段"]);
    expect(restored.storyboard).toHaveLength(2);
    expect(restored.stage).toBe("storyboard");
    expect(restored.scriptConfirmed).toBe(true);
    expect(restored.storyboardConfirmed).toBe(false);
  });

  it("does not restore a retired prompt from a completed research job", () => {
    const restored = applyProjectJobsToDraft(createEmptyWorkflow("project-a", true), [
      job({
        id: "research-old",
        job_type: "research",
        result_json: {
          research_status: "reference_ready",
          storyboard_plan: [{
            scene_index: 1,
            narration: "kept narration",
            media_prompt: "A non-identifying main battle tank at rest with neutral markings.",
          }],
        },
      }),
    ]);

    expect(restored.narrations).toEqual(["kept narration"]);
    expect(restored.storyboard).toEqual([]);
    expect(restored.research.activeJobId).toBeNull();
    expect(restored.research.stale).toBe(true);
  });

  it("keeps a generated script on the script stage for confirmation", () => {
    const restored = applyProjectJobsToDraft(createEmptyWorkflow("project-a"), [
      job({ result_json: { narrations: ["第一段", "第二段"] } }),
    ]);

    expect(restored.stage).toBe("script");
    expect(restored.scriptConfirmed).toBe(false);
  });

  it("restores a referenced script even when online enrichment degraded", () => {
    const restored = applyProjectJobsToDraft(createEmptyWorkflow("project-a", true), [
      job({
        params_json: { text: "东风火箭", mode: "reference" },
        result_json: {
          narrations: ["第一段", "第二段"],
          research_status: "reference_unavailable",
          warnings: ["search_unavailable"],
        },
      }),
    ]);

    expect(restored.narrations).toEqual(["第一段", "第二段"]);
    expect(restored.stage).toBe("script");
    expect(restored.research.status).toBe("reference_unavailable");
    expect(restored.research.warnings).toEqual(["search_unavailable"]);
  });

  it("restores navigation prerequisites after a completed video", () => {
    const draft = {
      ...createEmptyWorkflow("project-a"),
      storyboard: [{
        id: "scene-0",
        index: 0,
        narration: "第一段",
        visualDescription: "画面",
        mediaPrompt: "提示词",
        estimatedDuration: 3,
        assetType: "video" as const,
        status: "completed" as const,
      }],
    };
    const restored = applyProjectJobsToDraft(draft, [
      job({ id: "video-1", job_type: "video_generation", result_json: { video_url: "/final.mp4" } }),
    ]);

    expect(restored.scriptConfirmed).toBe(true);
    expect(restored.storyboardConfirmed).toBe(true);
  });

  it("does not apply another project's job result", () => {
    const draft = createEmptyWorkflow("project-a");
    const restored = applyProjectJobsToDraft(draft, [
      job({ project_id: "project-b", result_json: { narrations: ["串线数据"] } }),
    ]);

    expect(restored.narrations).toEqual([""]);
  });

  it("maps a completed reference snapshot into a storyboard with viewable sources", () => {
    const draft = createEmptyWorkflow("project-a", true);
    const restored = applyProjectJobsToDraft(draft, [
      job({
        id: "research-1",
        job_type: "research",
        result_json: {
          input_hash: "hash-1",
          script_revision: 2,
          research_status: "reference_ready",
          sources: [{ id: "source-1", title: "Reference source", url: "https://example.test/source" }],
          storyboard_plan: [
            {
              scene_index: 1,
              narration: "Verified narration",
              visual_description: "Verified exterior",
              media_prompt: "audited prompt",
              asset_type: "video",
              subject_id: "subject-1",
              claim_ids: ["claim-1"],
              visual_fact_ids: ["visual-1"],
              subject: {
                value: "generic aircraft",
                provenance: { claim_ids: ["claim-1"], visual_fact_ids: ["visual-1"], creative: false },
              },
              environment: { value: "apron", provenance: { claim_ids: ["claim-1"] } },
              opening_state: { value: "stationary", provenance: { claim_ids: ["claim-1"] } },
              action: { value: "inspection", provenance: { claim_ids: ["claim-1"] } },
              camera: { value: "wide shot", creative: true },
              composition: { value: "centered", creative: true },
              lighting: { value: "daylight", creative: true },
              ending_frame: { value: "profile", provenance: { claim_ids: ["claim-1"] } },
              fallback_level: "verified_generic",
              verification_status: "verified",
              negative_constraints: ["no logos"],
              warnings: [],
            },
          ],
        },
      }),
    ]);

    expect(restored.research).toMatchObject({
      mode: "verified",
      activeJobId: "research-1",
      inputHash: "hash-1",
      scriptRevision: 2,
      status: "reference_ready",
      sourceCount: 1,
      sources: [{ title: "Reference source", url: "https://example.test/source" }],
      stale: false,
    });
    expect(restored.storyboard[0]).toMatchObject({
      index: 0,
      researchJobId: "research-1",
      claimIds: ["claim-1"],
      mediaPrompt: "audited prompt",
      estimatedDuration: 5,
      verificationStatus: "verified",
    });
  });

  it("re-estimates legacy reference scene durations that are missing or defaulted to one", () => {
    const restored = applyProjectJobsToDraft(createEmptyWorkflow("project-a", true), [
      job({
        id: "research-duration",
        job_type: "research",
        result_json: {
          research_status: "reference_ready",
          storyboard_plan: [
            {
              scene_index: 1,
              narration: "12345678901234567890",
              media_prompt: "documentary shot",
              estimated_duration: 1,
            },
          ],
        },
      }),
    ]);

    expect(restored.storyboard[0].estimatedDuration).toBe(5);
  });

  it("preserves partial reference status from research jobs", () => {
    const restored = applyProjectJobsToDraft(createEmptyWorkflow("project-a", true), [
      job({
        id: "research-low",
        job_type: "research",
        result_json: {
          input_hash: "hash-low",
          script_revision: 3,
          research_status: "partial_reference",
          warnings: ["partial_reference_collection"],
          storyboard_plan: [
            {
              scene_index: 1,
              narration: "Low-confidence narration",
              media_prompt: "audited low-confidence prompt",
              verification_status: "low_confidence_verified",
              fallback_level: "verified_generic",
              warnings: ["single_source_verification"],
            },
          ],
        },
      }),
    ]);

    expect(restored.research.status).toBe("partial_reference");
    expect(restored.research.warnings).toEqual(["partial_reference_collection"]);
  });
});
