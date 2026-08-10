import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StoryboardStage } from "@/features/video/StoryboardStage";
import type { EditableStoryboardScene, WorkflowResearchState } from "@/features/video/workflow";
import type { ReferenceAsset } from "@/types/api";

const scene: EditableStoryboardScene = {
  id: "scene-1", index: 0, narration: "雷达开始搜索", visualDescription: "radar scans", mediaPrompt: "A radar array scans the horizon.", estimatedDuration: 5, assetType: "video", status: "draft", referenceAssetIds: ["asset-1"],
};
const asset: ReferenceAsset = {
  id: "asset-1", project_id: "project-1", filename: "radar.webp", mime_type: "image/webp", size_bytes: 1024, width: 640, height: 360, metadata_json: {}, url: "/radar.webp", created_at: "2026-08-10T00:00:00Z",
};

const unavailableResearch: WorkflowResearchState = {
  mode: "verified",
  activeJobId: "research-1",
  inputHash: null,
  scriptRevision: 1,
  status: "reference_unavailable",
  sourceCount: 0,
  sources: [],
  warnings: ["search_unavailable"],
  stale: false,
};

describe("storyboard reference status", () => {
  it("shows an unavailable message only after a real research warning", () => {
    const onGenerate = vi.fn();
    render(
      <StoryboardStage
        disabled={false}
        isGenerating={false}
        onChange={vi.fn()}
        onConfirm={vi.fn()}
        onGenerate={onGenerate}
        onModeChange={vi.fn()}
        research={unavailableResearch}
        researchCapabilityEnabled
        scenes={[]}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "联网事实增强暂不可用，本次已按快速模式生成。",
    );
    fireEvent.click(screen.getByRole("button", { name: "联网事实增强生成分镜" }));
    expect(onGenerate).toHaveBeenCalledOnce();
  });

  it("does not report a failure before online reference generation starts", () => {
    render(
      <StoryboardStage
        disabled={false}
        isGenerating={false}
        onChange={vi.fn()}
        onConfirm={vi.fn()}
        onGenerate={vi.fn()}
        onModeChange={vi.fn()}
        research={{ ...unavailableResearch, activeJobId: null }}
        researchCapabilityEnabled
        scenes={[]}
      />,
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("explains why an old subject-free fallback cannot be confirmed", () => {
    render(
      <StoryboardStage
        disabled={false}
        isGenerating={false}
        onChange={vi.fn()}
        onConfirm={vi.fn()}
        onGenerate={vi.fn()}
        onModeChange={vi.fn()}
        research={{ ...unavailableResearch, warnings: [] }}
        researchCapabilityEnabled
        scenes={[{
          id: "scene-1",
          index: 0,
          narration: "大炮发射弹丸",
          visualDescription: "",
          mediaPrompt: "A credible military technology subject in an ordinary environment.",
          estimatedDuration: 5,
          assetType: "video",
          status: "completed",
        }]}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("没有写明具体主体");
    expect(screen.getByRole("button", { name: "确认分镜，进入视频生成" })).toBeDisabled();
  });

  it("hides all equipment reference controls for LTX and shows them for H3", () => {
    const common = { disabled: false, isGenerating: false, onChange: vi.fn(), onConfirm: vi.fn(), onGenerate: vi.fn(), onModeChange: vi.fn(), research: { ...unavailableResearch, warnings: [] }, researchCapabilityEnabled: true, scenes: [scene], referenceAssets: [asset] };
    const { rerender } = render(<StoryboardStage {...common} referenceMode="standard" />);
    expect(screen.queryByText("装备视觉参考")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "添加参考图" })).not.toBeInTheDocument();

    rerender(<StoryboardStage {...common} referenceMode="h3" />);
    expect(screen.getAllByText("装备视觉参考").length).toBeGreaterThan(0);
  });

  it("preserves scene bindings when the generator mode changes away and back", () => {
    const common = { disabled: false, isGenerating: false, onChange: vi.fn(), onConfirm: vi.fn(), onGenerate: vi.fn(), onModeChange: vi.fn(), research: { ...unavailableResearch, warnings: [] }, researchCapabilityEnabled: true, scenes: [scene], referenceAssets: [asset] };
    const { rerender } = render(<StoryboardStage {...common} referenceMode="h3" />);
    expect(screen.getAllByAltText("radar.webp").length).toBeGreaterThan(0);
    rerender(<StoryboardStage {...common} referenceMode="standard" />);
    expect(screen.queryByText("装备视觉参考")).not.toBeInTheDocument();
    rerender(<StoryboardStage {...common} referenceMode="h3" />);
    expect(screen.getAllByAltText("radar.webp").length).toBeGreaterThan(0);
  });

  it("applies selected references to all scenes and clears bindings without deleting assets", () => {
    const onChange = vi.fn();
    render(<StoryboardStage disabled={false} isGenerating={false} onChange={onChange} onConfirm={vi.fn()} onGenerate={vi.fn()} onModeChange={vi.fn()} research={{ ...unavailableResearch, warnings: [] }} researchCapabilityEnabled scenes={[scene, { ...scene, id: "scene-2", index: 1, referenceAssetIds: [] }]} referenceAssets={[asset]} referenceMode="h3" />);
    fireEvent.click(screen.getByRole("button", { name: "选择 radar.webp" }));
    fireEvent.click(screen.getByRole("button", { name: /将已选参考应用到全部分镜/ }));
    expect(onChange).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({ referenceAssetIds: ["asset-1"] }),
      expect.objectContaining({ referenceAssetIds: ["asset-1"] }),
    ]));
    fireEvent.click(screen.getByRole("button", { name: "清除全部分镜绑定" }));
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ referenceAssetIds: [] }),
      expect.objectContaining({ referenceAssetIds: [] }),
    ]);
  });

  it("shows the reason when storyboard confirmation is disabled", () => {
    render(<StoryboardStage disabled={false} isGenerating={false} onChange={vi.fn()} onConfirm={vi.fn()} onGenerate={vi.fn()} onModeChange={vi.fn()} research={{ ...unavailableResearch, warnings: [] }} researchCapabilityEnabled scenes={[{ ...scene, narration: "" }]} />);
    expect(screen.getByRole("button", { name: "确认分镜，进入视频生成" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("SHOT 01 缺少解说词或英文生成提示词");
  });
});
