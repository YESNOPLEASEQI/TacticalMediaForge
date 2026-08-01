import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StoryboardStage } from "@/features/video/StoryboardStage";
import type { WorkflowResearchState } from "@/features/video/workflow";

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
      "联网参考暂不可用，本次已按普通模式生成。",
    );
    fireEvent.click(screen.getByRole("button", { name: "联网参考生成" }));
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
});
