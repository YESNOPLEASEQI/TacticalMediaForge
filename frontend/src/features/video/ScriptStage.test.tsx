import * as React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ScriptStage, type ScriptGenerationFeedback } from "@/features/video/ScriptStage";
import { createEmptyWorkflow } from "@/features/video/workflow";

function Harness({
  capabilityEnabled = true,
  feedback = { status: "idle", mode: "reference", sources: [], warnings: [] },
  generationError,
}: {
  capabilityEnabled?: boolean;
  feedback?: ScriptGenerationFeedback;
  generationError?: string;
}) {
  const [narrations, setNarrations] = React.useState(["第一段", "第二段", "第三段"]);
  const [scriptMode, setScriptMode] = React.useState<"reference" | "quick">("reference");
  return (
    <ScriptStage
      bgmFiles={[]}
      config={createEmptyWorkflow().config}
      disabled={false}
      generationError={generationError}
      generationFeedback={feedback}
      isGenerating={false}
      narrations={narrations}
      researchCapabilityEnabled={capabilityEnabled}
      scriptMode={scriptMode}
      onConfigChange={vi.fn()}
      onConfirm={vi.fn()}
      onGenerate={vi.fn()}
      onScriptModeChange={setScriptMode}
      onNarrationsChange={setNarrations}
      onSourceTextChange={vi.fn()}
      onTitleChange={vi.fn()}
      sourceText="雷达"
      templates={[]}
      title="测试"
    />
  );
}

describe("ScriptStage motion", () => {
  it("allows switching the script generation mode", async () => {
    render(<Harness />);
    const modeGroup = screen.getByLabelText("脚本生成模式");
    const quickButton = within(modeGroup).getByRole("button", { name: "快速生成" });
    fireEvent.click(quickButton);
    expect(quickButton).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps the following paragraph visible after deleting a middle item", async () => {
    render(<Harness />);
    fireEvent.click(await screen.findByRole("button", { name: "删除脚本段落 2" }));

    await waitFor(() => expect(screen.queryByDisplayValue("第二段")).not.toBeInTheDocument());
    const survivor = screen.getByDisplayValue("第三段").closest<HTMLElement>("[data-motion='script-paragraph']");
    expect(survivor).not.toBeNull();
    await waitFor(() => {
      expect(survivor).not.toHaveStyle({ opacity: "0" });
      expect(survivor).not.toHaveStyle({ visibility: "hidden" });
    });
  });

  it("disables online references when the capability is unavailable", () => {
    render(<Harness capabilityEnabled={false} />);
    expect(screen.getByRole("button", { name: "联网参考" })).toBeDisabled();
  });

  it("shows a persistent script generation error", () => {
    render(<Harness generationError="脚本生成超时，模型未返回完整内容。" />);
    expect(screen.getByRole("alert")).toHaveTextContent("脚本生成超时");
  });

  it("shows when online references are being collected", () => {
    render(<Harness feedback={{ status: "running", mode: "reference", sources: [], warnings: [] }} />);

    expect(screen.getByRole("status")).toHaveTextContent("正在联网获取参考资料并生成脚本");
  });

  it("reports successful fallback when online references are unavailable", () => {
    render(<Harness feedback={{
      status: "completed",
      mode: "reference",
      researchStatus: "reference_unavailable",
      sources: [],
      warnings: ["search_unavailable"],
    }} />);

    expect(screen.getByRole("status")).toHaveTextContent("脚本生成成功");
    expect(screen.getByRole("status")).toHaveTextContent("联网参考不可用");
    fireEvent.click(screen.getByText("查看参考来源与提示"));
    expect(screen.getByText("联网搜索暂不可用")).toBeInTheDocument();
  });

  it("shows successful online generation and its sources", () => {
    render(<Harness feedback={{
      status: "completed",
      mode: "reference",
      researchStatus: "reference_ready",
      sources: [{ title: "官方资料", url: "https://example.test/source" }],
      warnings: [],
    }} />);

    expect(screen.getByRole("status")).toHaveTextContent("已使用联网参考（1 个来源）");
    fireEvent.click(screen.getByText("查看参考来源与提示"));
    expect(screen.getByRole("link", { name: "官方资料" })).toHaveAttribute("href", "https://example.test/source");
  });
});
