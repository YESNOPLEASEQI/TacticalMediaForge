import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkflowStepNav } from "@/features/video/WorkflowStepNav";

describe("WorkflowStepNav", () => {
  it("locks storyboard and video until their prerequisites are confirmed", () => {
    const { container } = render(
      <WorkflowStepNav
        onChange={vi.fn()}
        scriptConfirmed={false}
        stage="script"
        storyboardConfirmed={false}
      />,
    );

    expect(screen.getByRole("button", { name: /分镜/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /视频/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /脚本/ })).toHaveAttribute("data-active", "true");
    expect(container.querySelectorAll(".rb-stepper__connector")).toHaveLength(2);
    expect(container.querySelector(".workflow-rail__progress")).toBeNull();
  });

  it("allows returning to completed stages", () => {
    const onChange = vi.fn();
    render(
      <WorkflowStepNav
        onChange={onChange}
        scriptConfirmed
        stage="video"
        storyboardConfirmed
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /脚本/ }));
    expect(onChange).toHaveBeenCalledWith("script");
  });
});
