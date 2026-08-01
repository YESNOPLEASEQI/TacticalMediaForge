import * as React from "react";
import { ChevronDown, ChevronUp, CircleAlert, Clock3, Download, FileVideo, Loader2, Square, Video } from "lucide-react";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { AnimatedList } from "@/components/react-bits/AnimatedList";
import { SpotlightCard } from "@/components/react-bits/SpotlightCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { gsap, useGSAP } from "@/lib/gsap";
import { didSemanticValueChange } from "@/lib/motionState";
import { formatBytes, formatDuration } from "@/lib/utils";
import type { Task } from "@/types/api";
import { VideoPreview } from "@/features/video/VideoPreview";

interface GenerationStatusPanelProps { isCancelling: boolean; onCancel: () => void; task?: Task; }

const stages = ["等待处理", "进行中", "已完成"];

function statusLabel(status?: Task["status"]) {
  if (status === "pending") return "等待处理";
  if (status === "running") return "进行中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "生成失败";
  if (status === "cancelled") return "已取消";
  return "等待开始";
}

function statusVariant(status?: Task["status"]) {
  if (status === "completed") return "success" as const;
  if (status === "failed") return "destructive" as const;
  if (status === "cancelled") return "warning" as const;
  if (status === "pending" || status === "running") return "default" as const;
  return "secondary" as const;
}

function progressValue(task?: Task) {
  if (task?.status === "completed") return 100;
  return task?.progress?.percentage ?? 0;
}

function stageIndex(task?: Task) {
  if (task?.status === "completed") return 2;
  if (task?.status === "pending") return 0;
  if (task?.status === "running") return 1;
  return task ? 1 : 0;
}

function requestDetail(task?: Task) {
  const params = task?.request_params;
  if (!params) return [];
  const provider = typeof params.provider === "string" ? params.provider : null;
  const workflow = typeof params.media_workflow === "string" ? params.media_workflow : typeof params.workflow === "string" ? params.workflow : null;
  return [provider, workflow].filter((value): value is string => Boolean(value));
}

export function GenerationStatusPanel({ isCancelling, onCancel, task }: GenerationStatusPanelProps) {
  const [showTechnical, setShowTechnical] = React.useState(false);
  const panelRef = React.useRef<HTMLDivElement>(null);
  const previousProgress = React.useRef<number | undefined>(undefined);
  const previousStatus = React.useRef<Task["status"] | undefined>(undefined);
  const result = task?.result;
  const canCancel = task?.status === "pending" || task?.status === "running";
  const message = task?.progress?.message || statusLabel(task?.status);
  const generationMethods = requestDetail(task);
  const progress = progressValue(task);

  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add({ reduceMotion: "(prefers-reduced-motion: reduce)", allowMotion: "(prefers-reduced-motion: no-preference)" }, (context) => {
      const reduced = Boolean(context.conditions?.reduceMotion);
      const from = previousProgress.current ?? progress;
      const bar = panelRef.current?.querySelector<HTMLElement>("[data-motion='generation-progress-bar']");
      const value = panelRef.current?.querySelector<HTMLElement>("[data-testid='generation-progress-value']");
      if (bar) gsap.fromTo(bar, { scaleX: from / 100 }, { scaleX: progress / 100, duration: reduced ? 0.2 : 0.62, ease: "interface", overwrite: "auto" });
      if (value) {
        const counter = { value: from };
        gsap.to(counter, { value: progress, duration: reduced ? 0.2 : 0.58, ease: "interface", overwrite: "auto", onUpdate: () => { value.textContent = `${Math.round(counter.value)}%`; } });
      }

      const status = task?.status;
      const statusChanged = status !== undefined && didSemanticValueChange(previousStatus.current, status);
      const systemState = panelRef.current?.querySelector<HTMLElement>("[data-motion='system-state']");
      if (statusChanged && systemState && !reduced) {
        gsap.fromTo(systemState, { autoAlpha: 0.45 }, { autoAlpha: 1, duration: 0.42, scrambleText: { text: systemState.textContent ?? "", chars: "01—", speed: 0.55 }, ease: "interface", overwrite: "auto" });
      }

      if (status === "failed" && (statusChanged || previousStatus.current === undefined)) {
        gsap.fromTo("[data-motion='generation-error']", { autoAlpha: 0, x: reduced ? 0 : -12, scale: reduced ? 1 : 0.985 }, { autoAlpha: 1, x: 0, scale: 1, duration: reduced ? 0.2 : 0.46, ease: "impact", overwrite: "auto" });
      }
      if (status === "completed" && result?.video_url && (statusChanged || previousStatus.current === undefined)) {
        gsap.from("[data-motion='result-preview'], [data-motion='result-meta'], [data-motion='result-actions']", { autoAlpha: 0, y: reduced ? 0 : 16, scale: reduced ? 1 : 0.99, duration: reduced ? 0.18 : 0.52, stagger: reduced ? 0 : 0.11, ease: "reveal", overwrite: "auto" });
      }
      previousProgress.current = progress;
      previousStatus.current = status;
    });
    return () => media.revert();
  }, { scope: panelRef, dependencies: [progress, task?.status, result?.video_url], revertOnUpdate: true });

  return (
    <div data-status={task?.status ?? "idle"} data-testid="generation-status-panel" ref={panelRef}><SpotlightCard>
      <SectionPanel actions={<Badge variant={statusVariant(task?.status)}>{statusLabel(task?.status)}</Badge>} className="h-full" title="生成进度">
        <div className="space-y-5">
          <div className="ops-panel-muted p-4">
            <div className="mb-2 flex items-center justify-between gap-3"><p className="ops-kicker" data-motion="system-state">SYSTEM · {statusLabel(task?.status)}</p><span className="font-data text-sm text-primary" data-testid="generation-progress-value">{Math.round(progress)}%</span></div>
            <div className="mb-3 flex items-center gap-2 text-sm font-medium">
              {canCancel ? <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" /> : <Clock3 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
              <span>{message}</span>
            </div>
            <div aria-valuemax={100} aria-valuemin={0} aria-valuenow={progress} className="generation-progress" role="progressbar"><span data-motion="generation-progress-bar"><i aria-hidden="true" /></span></div>
          </div>

          <div><p className="mb-2 text-xs text-muted-foreground">处理阶段</p><AnimatedList activeIndex={stageIndex(task)} items={stages} /></div>

          {task?.task_id || generationMethods.length ? (
            <div className="border-t border-border/60 pt-2">
              <Button aria-expanded={showTechnical} className="w-full justify-between" onClick={() => setShowTechnical((value) => !value)} size="sm" type="button" variant="ghost">
                技术详情
                {showTechnical ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
              {showTechnical ? (
                <dl className="mt-2 space-y-2 rounded-md border border-border/60 bg-background/30 p-3 text-xs">
                  {task?.task_id ? <div><dt className="text-muted-foreground">任务编号</dt><dd className="mt-0.5 break-all font-data">{task.task_id}</dd></div> : null}
                  {generationMethods.length ? <div><dt className="text-muted-foreground">生成方式</dt><dd className="mt-0.5 flex flex-wrap gap-1.5 font-data">{generationMethods.map((method) => <span className="rounded-sm bg-muted px-1.5 py-0.5" key={method}>{method}</span>)}</dd></div> : null}
                </dl>
              ) : null}
            </div>
          ) : null}

          {canCancel ? <Button className="w-full" isLoading={isCancelling} onClick={onCancel} type="button" variant="secondary"><Square className="h-4 w-4" aria-hidden="true" />取消生成</Button> : null}

            {task?.status === "failed" ? <div className="rounded-md border border-destructive/45 bg-destructive/10 p-4 text-sm" data-motion="generation-error" role="alert"><div className="mb-1 flex items-center gap-2 font-medium text-foreground"><CircleAlert className="h-4 w-4 text-destructive" aria-hidden="true" />生成失败</div><p className="text-muted-foreground">{task.error || "生成未能完成，请稍后重试。"}</p></div> : null}
            {result?.video_url ? (
              <div className="space-y-4">
                <div data-motion="result-preview"><VideoPreview src={result.video_url} /></div>
                <div className="grid gap-3 sm:grid-cols-2" data-motion="result-meta">
                  <div className="ops-panel-muted p-3"><div className="flex items-center gap-2 text-xs text-muted-foreground"><Video className="h-4 w-4" aria-hidden="true" />时长</div><p className="mt-1 text-sm font-medium">{formatDuration(result.duration)}</p></div>
                  <div className="ops-panel-muted p-3"><div className="flex items-center gap-2 text-xs text-muted-foreground"><FileVideo className="h-4 w-4" aria-hidden="true" />文件大小</div><p className="mt-1 text-sm font-medium">{formatBytes(result.file_size)}</p></div>
                </div>
                <div data-motion="result-actions"><Button asChild className="w-full" variant="secondary"><a href={result.video_url} rel="noreferrer" target="_blank"><Download className="h-4 w-4" aria-hidden="true" />打开成片</a></Button></div>
              </div>
            ) : null}
        </div>
      </SectionPanel>
    </SpotlightCard></div>
  );
}
