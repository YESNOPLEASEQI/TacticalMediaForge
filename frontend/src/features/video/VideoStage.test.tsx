import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Task } from "@/types/api";
import { VideoStage } from "@/features/video/VideoStage";
import { createEmptyWorkflow, type VideoWorkflowConfig } from "@/features/video/workflow";
import * as React from "react";

const baseProps = {
  bgmFiles: [],
  config: createEmptyWorkflow().config,
  templates: [],
  onBack: vi.fn(),
  onConfigChange: vi.fn(),
};

const completedTask: Task = {
  task_id: "task-1",
  task_type: "video_generation",
  status: "completed",
  created_at: "2026-07-13T00:00:00Z",
  result: { video_url: "/api/files/final.mp4" },
};

describe("VideoStage", () => {
  it("allows submission while project history is still restoring", () => {
    const onGenerate = vi.fn();
    render(
      <VideoStage
        {...baseProps}
        canGenerate
        isCancelling={false}
        isRestoringTask
        isSubmitting={false}
        onCancel={() => undefined}
        onGenerate={onGenerate}
        scenes={[]}
      />,
    );

    const button = screen.getByText("开始生成视频").closest("button");
    expect(button).not.toBeNull();
    expect(button).toBeEnabled();
    fireEvent.click(button!);
    expect(onGenerate).toHaveBeenCalledOnce();
  });

  it("allows a completed video to be regenerated after confirmed edits", async () => {
    const onGenerate = vi.fn();
    render(
      <VideoStage
        {...baseProps}
        hasUnsubmittedChanges
        isCancelling={false}
        isSubmitting={false}
        onCancel={() => undefined}
        onGenerate={onGenerate}
        scenes={[]}
        task={completedTask}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: /按当前修改生成新版本/ }));
    expect(onGenerate).toHaveBeenCalledOnce();
  });

  it("shows H3 reference counts in preflight and keeps output settings editable", () => {
    function Harness() {
      const [config, setConfig] = React.useState<VideoWorkflowConfig>({ ...createEmptyWorkflow().config, bgmEnabled: true, bgmPath: "bgm/default.mp3", bgmVolume: 0.3, referenceMode: "h3" });
      return <VideoStage bgmFiles={[{ name: "default.mp3", path: "bgm/default.mp3", source: "default" }]} canGenerate config={config} isCancelling={false} isSubmitting={false} onBack={vi.fn()} onCancel={vi.fn()} onConfigChange={setConfig} onGenerate={vi.fn()} referenceAssets={[{ id: "asset-1", project_id: "p", filename: "tank.webp", mime_type: "image/webp", size_bytes: 1, width: 10, height: 10, metadata_json: {}, url: "/tank.webp", created_at: "2026-08-10T00:00:00Z" }]} referenceMode="h3" scenes={[{ id: "s1", index: 0, narration: "坦克前进", visualDescription: "tank", mediaPrompt: "A tank advances across a field.", estimatedDuration: 5, assetType: "video", status: "draft", referenceAssetIds: ["asset-1"] }]} templates={[]} />;
    }
    render(<Harness />);
    expect(screen.getByText("1 张 · 1/1 个分镜已绑定")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("背景音乐音量"), { target: { value: "0.6" } });
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getAllByAltText("tank.webp").length).toBeGreaterThan(0);
  });
});
