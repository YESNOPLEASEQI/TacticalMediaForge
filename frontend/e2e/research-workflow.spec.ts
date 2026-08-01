import { expect, test, type Page, type Route } from "@playwright/test";

const project = {
  id: "project-a",
  title: "Aircraft",
  description: null,
  project_type: "video_agent",
  status: "active",
  current_stage: "storyboard",
  source_text: "Aircraft",
  thumbnail_path: null,
  owner_id: null,
  settings_json: {
    workspace_draft: {
      version: 1,
      sessionId: "project-a",
      stage: "storyboard",
      sourceText: "Aircraft",
      title: "Aircraft",
      narrations: ["Verified narration"],
      scriptConfirmed: true,
      storyboard: [],
      storyboardConfirmed: false,
      contentRevision: 0,
      submittedRevision: 0,
      research: {
        mode: "verified",
        activeJobId: null,
        inputHash: null,
        scriptRevision: 1,
        verificationStatus: "unverified",
        stale: false,
      },
      config: {
        nScenes: 1,
        frameTemplate: "1080x1920/video_default.html",
        mediaWorkflow: "selfhost/video_ltx2_3_t2v.json",
        bgmEnabled: false,
        bgmPath: "",
        bgmVolume: 0.3,
      },
    },
  },
  created_at: "2026-07-22T00:00:00Z",
  updated_at: "2026-07-22T00:00:00Z",
  archived_at: null,
  deleted_at: null,
};

function researchJob(id: string) {
  const provenance = { claim_ids: ["claim-1"], visual_fact_ids: ["visual-1"], creative: false };
  return {
    id,
    project_id: "project-a",
    parent_job_id: id === "research-2" ? "research-1" : null,
    job_type: "research",
    provider: "local",
    status: "completed",
    progress: 100,
    external_job_id: id,
    params_json: {},
    result_json: {
      input_hash: `hash-${id}`,
      script_revision: id === "research-2" ? 2 : 1,
      research_status: "reference_ready",
      verification_status: "verified",
      sources: [{ id: "source-1", url: "https://example.org/report", title: "Report" }],
      claims: [{ id: "claim-1", statement: "Verified exterior inspection", confidence: 0.9, evidence_quotes: [{ source_id: "source-1", quote: "exterior inspection" }] }],
      visual_facts: [{ id: "visual-1", allowed_detail: "generic aircraft", confidence: 0.9, forbidden_inference: ["specific unit marking"] }],
      warnings: [],
      storyboard_plan: [{
        scene_index: 1,
        narration: "Verified narration",
        visual_description: "Verified aircraft exterior",
        media_prompt: "generic aircraft; apron; stationary; exterior inspection; wide shot; centered; daylight; exterior profile; authentic military documentary",
        asset_type: "video",
        subject_id: "subject-1",
        claim_ids: ["claim-1"],
        visual_fact_ids: ["visual-1"],
        subject: { value: "generic aircraft", provenance },
        environment: { value: "apron", provenance },
        opening_state: { value: "stationary", provenance },
        action: { value: "exterior inspection", provenance },
        camera: { value: "wide shot", creative: true },
        composition: { value: "centered", creative: true },
        lighting: { value: "daylight", creative: true },
        ending_frame: { value: "exterior profile", provenance },
        negative_constraints: ["no logos"],
        fallback_level: "verified_generic",
        verification_status: "verified",
        warnings: [],
      }],
    },
    error_message: null,
    progress_stage: "rendering_prompts",
    progress_message: "complete",
    created_at: id === "research-2" ? "2026-07-22T00:02:00Z" : "2026-07-22T00:01:00Z",
    started_at: "2026-07-22T00:01:00Z",
    completed_at: "2026-07-22T00:01:30Z",
  };
}

async function mockApi(page: Page) {
  let jobs: ReturnType<typeof researchJob>[] = [];
  let videoRequest: Record<string, unknown> | null = null;
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api") && url.pathname !== "/health") return route.continue();
    if (url.pathname === "/health") return json(route, { status: "healthy", research_enabled: true, research_default_mode: "verified" });
    if (url.pathname === "/api/resources/templates") return json(route, { success: true, message: "ok", templates: [{ name: "video", display_name: "Video", size: "1080x1920", width: 1080, height: 1920, orientation: "portrait", path: "1080x1920/video_default.html", key: "1080x1920/video_default.html" }] });
    if (url.pathname === "/api/resources/bgm") return json(route, { success: true, message: "ok", bgm_files: [] });
    if (url.pathname === "/api/resources/workflows/media") return json(route, { workflows: [{ key: "selfhost/video_ltx2_3_t2v.json", display_name: "LTX" }] });
    if (url.pathname === "/api/projects/project-a" && route.request().method() === "GET") return json(route, project);
    if (url.pathname === "/api/projects/project-a" && route.request().method() === "PATCH") return json(route, { ...project, ...(route.request().postDataJSON() as object) });
    if (url.pathname === "/api/sessions/project-a") return json(route, { detail: "not found" }, 404);
    if (url.pathname === "/api/jobs") return json(route, jobs);
    if (url.pathname === "/api/content/research/async") { jobs = [researchJob("research-1")]; return json(route, { job_id: "research-1" }, 202); }
    if (url.pathname === "/api/content/research/research-1/retry") { jobs = [researchJob("research-2"), ...jobs]; return json(route, { job_id: "research-2" }, 202); }
    if (url.pathname === "/api/video/generate/async") { videoRequest = route.request().postDataJSON(); return json(route, { task_id: "video-1" }); }
    return json(route, { detail: `unmocked ${url.pathname}` }, 404);
  });
  return { videoRequest: () => videoRequest };
}

test("verified storyboard research remains explicit, stale-aware, and traceable", async ({ page }) => {
  const capture = await mockApi(page);
  await page.goto("/#generate/project/project-a");

  await expect(page.getByRole("button", { name: "联网参考", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "联网参考生成" }).click();
  await expect(page.getByLabel("英文生成提示词")).toHaveValue(/generic aircraft/);
  await page.getByText("查看参考来源与提示").click();
  await expect(page.getByRole("link", { name: "Report" })).toBeVisible();

  await page.getByRole("button", { name: "脚本", exact: true }).click();
  await page.getByLabel("项目标题").fill("Aircraft updated");
  await page.getByRole("button", { name: "分镜", exact: true }).click();
  await page.getByRole("button", { name: "重新联网参考生成" }).click();

  await page.getByRole("button", { name: "确认分镜，进入视频生成" }).click();
  await page.getByRole("button", { name: "开始生成视频" }).click();
  await expect.poll(() => capture.videoRequest()).not.toBeNull();
  expect(capture.videoRequest()).toMatchObject({
    verification_mode: "verified",
    script_revision: 2,
    confirmed_storyboard: [{ research_job_id: "research-2", claim_ids: ["claim-1"] }],
  });
});
