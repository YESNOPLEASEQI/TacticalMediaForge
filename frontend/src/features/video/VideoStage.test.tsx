import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Task } from "@/types/api";
import { VideoStage } from "@/features/video/VideoStage";

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
        hasUnsubmittedChanges
        isCancelling={false}
        isSubmitting={false}
        onCancel={() => undefined}
        onGenerate={onGenerate}
        scenes={[]}
        task={completedTask}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: /按当前修改重新生成视频/ }));
    expect(onGenerate).toHaveBeenCalledOnce();
  });
});
