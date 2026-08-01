import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GenerationStatusPanel } from "@/features/video/GenerationStatusPanel";
import type { Task } from "@/types/api";

const task: Task = { task_id: "task-secret", task_type: "video_generation", status: "running", progress: { current: 60, total: 100, percentage: 60, message: "正在处理第 3 个镜头" }, created_at: "2026-07-14T00:00:00Z", request_params: { provider: "local", media_workflow: "video.json" } };

describe("generation status panel", () => {
  it("uses generic stages and hides technical details by default", () => {
    render(<GenerationStatusPanel isCancelling={false} onCancel={vi.fn()} task={task} />);
    expect(screen.getByTestId("generation-status-panel")).toHaveAttribute("data-status", "running");
    expect(screen.getByTestId("generation-progress-value")).toHaveTextContent("60%");
    expect(screen.getByText("正在处理第 3 个镜头")).toBeInTheDocument();
    expect(screen.getByText("等待处理")).toBeInTheDocument();
    expect(screen.getAllByText("进行中").length).toBeGreaterThan(0);
    expect(screen.queryByText("正在合成")).not.toBeInTheDocument();
    expect(screen.getByText("已完成")).toBeInTheDocument();
    expect(screen.queryByText("合成音频")).not.toBeInTheDocument();
    expect(screen.queryByText("Task ID: task-secret")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "技术详情" }));
    expect(screen.getByText("task-secret")).toBeInTheDocument();
    expect(screen.getByText("video.json")).toBeInTheDocument();
  });
});
