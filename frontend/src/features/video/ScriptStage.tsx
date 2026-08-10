import * as React from "react";
import { CheckCircle2, CircleAlert, FilePlus2, Plus, Sparkles, Trash2 } from "lucide-react";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { SpotlightCard } from "@/components/react-bits/SpotlightCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { GenerationModeSelector } from "@/features/video/ResearchModeSelector";
import { researchWarningLabel } from "@/features/video/researchWarnings";
import type { ResearchStatus } from "@/types/api";
import type { VideoWorkflowConfig } from "@/features/video/workflow";
import { gsap, useGSAP } from "@/lib/gsap";

export interface ScriptGenerationFeedback {
  status: "idle" | "running" | "completed" | "failed" | "cancelled";
  mode: "reference" | "quick";
  researchStatus?: ResearchStatus;
  sources: Array<{ title: string; url: string }>;
  warnings: string[];
}

interface ScriptStageProps {
  sourceText: string;
  title: string;
  narrations: string[];
  scriptMode: "reference" | "quick";
  researchCapabilityEnabled: boolean;
  config: VideoWorkflowConfig;
  disabled: boolean;
  isGenerating: boolean;
  generationError?: string;
  generationFeedback: ScriptGenerationFeedback;
  onSourceTextChange: (value: string) => void;
  onTitleChange: (value: string) => void;
  onNarrationsChange: (value: string[]) => void;
  onConfigChange: (value: VideoWorkflowConfig) => void;
  onGenerate: () => void;
  onScriptModeChange: (value: "reference" | "quick") => void;
  onConfirm: () => void;
}

export function ScriptStage(props: ScriptStageProps) {
  const stageRef = React.useRef<HTMLDivElement>(null);
  const previousLength = React.useRef(0);
  const wasGenerating = React.useRef(false);
  const updateNarration = (index: number, value: string) => {
    props.onNarrationsChange(props.narrations.map((item, position) => position === index ? value : item));
  };
  const hasScript = props.narrations.some((paragraph) => paragraph.trim());
  const feedbackMessage = (() => {
    const feedback = props.generationFeedback;
    if (feedback.status === "running") {
      return feedback.mode === "reference"
        ? "正在联网获取参考资料并生成脚本…"
        : "正在使用大模型生成脚本…";
    }
    if (feedback.status === "cancelled") return "脚本生成已取消";
    if (feedback.status !== "completed") return null;
    if (feedback.mode === "quick") return "脚本生成成功（快速模式）";
    if (feedback.researchStatus === "reference_ready") {
      return `脚本生成成功，已使用联网事实增强（${feedback.sources.length} 个来源）`;
    }
    if (feedback.researchStatus === "partial_reference") {
      return `脚本生成成功，已使用部分可用参考（${feedback.sources.length} 个来源）`;
    }
    return "脚本生成成功；联网事实增强不可用，已自动降级为快速模式";
  })();
  const { contextSafe } = useGSAP({ scope: stageRef });

  useGSAP(() => {
    const generationCompleted = wasGenerating.current && !props.isGenerating;
    const startIndex = generationCompleted ? 0 : previousLength.current;
    const paragraphs = Array.from(stageRef.current?.querySelectorAll<HTMLElement>("[data-motion='script-paragraph']") ?? []).slice(startIndex);
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    if (paragraphs.length) gsap.fromTo(paragraphs, { autoAlpha: 0, x: reduced ? 0 : -14, y: reduced ? 0 : 8 }, { autoAlpha: 1, x: 0, y: 0, duration: reduced ? 0.16 : 0.42, stagger: reduced ? 0 : 0.065, ease: "reveal", overwrite: "auto" });
    previousLength.current = props.narrations.length;
    wasGenerating.current = props.isGenerating;
  }, { scope: stageRef, dependencies: [props.narrations.length, props.isGenerating], revertOnUpdate: true });

  const removeParagraph = contextSafe((index: number) => {
    const apply = () => props.onNarrationsChange(props.narrations.filter((_, position) => position !== index));
    const target = stageRef.current?.querySelector<HTMLElement>(`[data-paragraph-index='${index}']`);
    if (!target || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { apply(); return; }
    gsap.to(target, {
      autoAlpha: 0,
      x: 18,
      scale: 0.99,
      duration: 0.26,
      ease: "interface",
      overwrite: "auto",
      onComplete: () => {
        // Index keys can reuse this node for the following paragraph after deletion.
        gsap.set(target, { clearProps: "transform,opacity,visibility" });
        apply();
      },
    });
  });

  return (
    <div ref={stageRef}><SpotlightCard>
      <SectionPanel
        actions={<span className="font-data text-xs text-muted-foreground">{props.narrations.length} 段</span>}
        title="完整脚本编辑器"
      >
        <div className="space-y-5">
          <div className="grid gap-4 lg:grid-cols-[1fr_220px]">
            <div className="space-y-2">
              <label className="control-label" htmlFor="workflow-title">项目标题</label>
              <Input id="workflow-title" disabled={props.disabled} value={props.title} onChange={(event) => props.onTitleChange(event.target.value)} placeholder="可选，留空时由后端生成" />
            </div>
            <div className="space-y-2">
              <label className="control-label" htmlFor="workflow-scenes">目标段落数</label>
              <Input id="workflow-scenes" disabled={props.disabled} min={1} max={20} type="number" value={props.config.nScenes} onChange={(event) => props.onConfigChange({ ...props.config, nScenes: Math.max(1, Number(event.target.value) || 1) })} />
            </div>
          </div>

          <div className="space-y-2">
            <label className="control-label" htmlFor="workflow-source">选题或原始文案</label>
            <Textarea id="workflow-source" disabled={props.disabled} value={props.sourceText} onChange={(event) => props.onSourceTextChange(event.target.value)} placeholder="例如：解释相控阵雷达如何同时追踪多个目标" />
            <div className="space-y-2">
              <p className="control-label">内容依据</p>
              <GenerationModeSelector
                ariaLabel="内容依据"
                capabilityEnabled={props.researchCapabilityEnabled}
                disabled={props.disabled || props.isGenerating}
                mode={props.scriptMode}
                onChange={props.onScriptModeChange}
              />
            </div>
            <Button disabled={props.disabled || !props.sourceText.trim()} isLoading={props.isGenerating} onClick={props.onGenerate} type="button" variant="secondary">
              <Sparkles className="h-4 w-4" />生成脚本段落
            </Button>
            {feedbackMessage ? (
              <div className="rounded-md border border-border/70 bg-background/35 px-3 py-2 text-sm text-muted-foreground">
                <p role="status">{feedbackMessage}</p>
                {props.generationFeedback.sources.length || props.generationFeedback.warnings.length ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer">查看参考来源与提示</summary>
                    {props.generationFeedback.sources.length ? (
                      <ul className="mt-2 space-y-1">
                        {props.generationFeedback.sources.map((source) => (
                          <li key={source.url}>
                            <a className="underline underline-offset-2" href={source.url} rel="noreferrer" target="_blank">
                              {source.title}
                            </a>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {props.generationFeedback.warnings.length ? (
                      <ul className="mt-2 list-disc space-y-1 pl-5">
                        {props.generationFeedback.warnings.map((warning) => (
                          <li key={warning}>{researchWarningLabel(warning)}</li>
                        ))}
                      </ul>
                    ) : null}
                  </details>
                ) : null}
              </div>
            ) : null}
            {props.generationError ? (
              <div className="rounded-md border border-destructive/45 bg-destructive/10 p-3 text-sm" role="alert">
                <div className="flex items-center gap-2 font-medium text-foreground">
                  <CircleAlert className="h-4 w-4 text-destructive" aria-hidden="true" />脚本生成未完成
                </div>
                <p className="mt-1 text-muted-foreground">{props.generationError}</p>
              </div>
            ) : null}
          </div>

          <div className="script-editor" aria-label="脚本段落编辑器">
            <div className="script-editor__header">
              <p className="font-display text-base font-semibold">解说脚本</p>
              <Button disabled={props.disabled} onClick={() => props.onNarrationsChange([...props.narrations, ""])} size="sm" type="button" variant="ghost"><Plus className="h-4 w-4" />添加段落</Button>
            </div>
            {props.narrations.map((paragraph, index) => (
              <div className="script-paragraph" data-motion="script-paragraph" data-paragraph-index={index} key={`paragraph-${index}`}>
                <span className="script-paragraph__index">{String(index + 1).padStart(2, "0")}</span>
                <Textarea aria-label={`脚本段落 ${index + 1}`} disabled={props.disabled} value={paragraph} onChange={(event) => updateNarration(index, event.target.value)} placeholder={`第 ${index + 1} 段解说词`} />
                <Button aria-label={`删除脚本段落 ${index + 1}`} disabled={props.disabled || props.narrations.length === 1} onClick={() => removeParagraph(index)} size="icon" type="button" variant="ghost"><Trash2 className="h-4 w-4" /></Button>
              </div>
            ))}
          </div>

          <Button className="w-full" disabled={props.disabled || !hasScript} onClick={props.onConfirm} type="button">
            {hasScript ? <CheckCircle2 className="h-4 w-4" /> : <FilePlus2 className="h-4 w-4" />}确认脚本，进入分镜
          </Button>
        </div>
      </SectionPanel>
    </SpotlightCard></div>
  );
}
