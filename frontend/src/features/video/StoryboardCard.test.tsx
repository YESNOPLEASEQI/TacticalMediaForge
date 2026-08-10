import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StoryboardCard } from "@/features/video/StoryboardCard";
import type { EditableStoryboardScene } from "@/features/video/workflow";
import type { ReferenceAsset } from "@/types/api";

const scene: EditableStoryboardScene = { id: "scene-0", index: 0, narration: "解说内容", visualDescription: "雷达阵列画面", mediaPrompt: "cinematic radar", estimatedDuration: 6, assetType: "video", status: "draft", referenceAssetIds: [] };

describe("storyboard card", () => {
  it("shows only the English generation prompt and keeps legacy fields synchronized", () => {
    const onChange = vi.fn();
    render(<StoryboardCard onChange={onChange} scene={scene} />);

    expect(screen.getByRole("article")).toHaveAttribute("data-scene-id", scene.id);
    expect(screen.getByText("SHOT 01")).toBeInTheDocument();
    expect(screen.getByText("6 秒")).toBeInTheDocument();
    expect(screen.getByLabelText("英文生成提示词")).toHaveValue("cinematic radar");
    expect(screen.queryByLabelText("画面描述")).not.toBeInTheDocument();
    expect(screen.getByText("直接用于图片或视频生成，仅允许英文。")).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("cinematic radar"), { target: { value: "updated prompt" } });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      mediaPrompt: "updated prompt",
      visualDescription: "updated prompt",
    }));
    expect(screen.queryByText(/重新生成此分镜/)).not.toBeInTheDocument();
  });

  it("uses list position for the displayed shot number", () => {
    render(<StoryboardCard displayIndex={0} scene={{ ...scene, index: 5 }} />);

    expect(screen.getByText("SHOT 01")).toBeInTheDocument();
  });

  it("shows an inline error for Chinese generation prompts", () => {
    render(<StoryboardCard scene={{ ...scene, mediaPrompt: "雷达 tracking shot" }} />);

    expect(screen.getByLabelText("英文生成提示词")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("提示词包含中文，无法确认或提交。");
  });

  it("keeps research-generated storyboard fields editable", () => {
    render(
      <StoryboardCard
        scene={{ ...scene, verificationStatus: "verified", fallbackLevel: "verified_specific" }}
      />,
    );

    expect(screen.getByDisplayValue("解说内容")).toBeEnabled();
    expect(screen.getByDisplayValue("cinematic radar")).toBeEnabled();
    expect(screen.queryByText("高可信核验")).not.toBeInTheDocument();
  });

  it("does not expose research confidence metadata", () => {
    render(
      <StoryboardCard
        scene={{
          ...scene,
          verificationStatus: "low_confidence_verified",
          fallbackLevel: "verified_generic",
          warnings: ["single_source_verification"],
        }}
      />,
    );

    expect(screen.queryByText("低置信核验")).not.toBeInTheDocument();
    expect(screen.queryByText("已验证通用")).not.toBeInTheDocument();
  });

  it("states the four-reference limit on an H3 shot", () => {
    const assets: ReferenceAsset[] = Array.from({ length: 4 }, (_, index) => ({
      id: `asset-${index}`,
      project_id: "project-1",
      filename: `reference-${index}.jpg`,
      mime_type: "image/jpeg",
      size_bytes: 1024,
      width: 640,
      height: 360,
      metadata_json: {},
      url: `/reference-${index}.jpg`,
      created_at: "2026-08-10T00:00:00Z",
    }));
    render(<StoryboardCard referenceAssets={assets} scene={{ ...scene, referenceAssetIds: assets.map((asset) => asset.id) }} showReferences />);

    expect(screen.getByRole("status")).toHaveTextContent("已达到每镜 4 张参考图上限");
  });
});
