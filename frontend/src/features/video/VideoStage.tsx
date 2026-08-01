import * as React from "react";
import { Film } from "lucide-react";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { SpotlightCard } from "@/components/react-bits/SpotlightCard";
import { Button } from "@/components/ui/button";
import type { Task } from "@/types/api";
import { GenerationStatusPanel } from "@/features/video/GenerationStatusPanel";
import { StoryboardCard } from "@/features/video/StoryboardCard";
import type { EditableStoryboardScene } from "@/features/video/workflow";
import { gsap, useGSAP } from "@/lib/gsap";

interface VideoStageProps {
  scenes: EditableStoryboardScene[];
  task?: Task;
  isSubmitting: boolean;
  isCancelling: boolean;
  isRestoringTask?: boolean;
  hasUnsubmittedChanges?: boolean;
  onGenerate: () => void;
  onCancel: () => void;
  canGenerate?: boolean;
  generationBlockReason?: string;
}

export function VideoStage({ scenes, task, isSubmitting, isCancelling, isRestoringTask = false, hasUnsubmittedChanges = false, onGenerate, onCancel, canGenerate = true, generationBlockReason }: VideoStageProps) {
  const stageRef = React.useRef<HTMLDivElement>(null);
  const running = task?.status === "pending" || task?.status === "running";

  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add({ reduceMotion: "(prefers-reduced-motion: reduce)", allowMotion: "(prefers-reduced-motion: no-preference)" }, (context) => {
      const reduced = Boolean(context.conditions?.reduceMotion);
      const timeline = gsap.timeline({ defaults: { ease: "reveal", overwrite: "auto" } });
      timeline
        .from("[data-motion='video-system-label']", { autoAlpha: 0, y: reduced ? 0 : 8, duration: reduced ? 0.16 : 0.35 })
        .from("[data-motion='video-scenes']", { autoAlpha: 0, x: reduced ? 0 : -18, scale: reduced ? 1 : 0.992, duration: reduced ? 0.18 : 0.55 }, "-=0.14")
        .from("[data-motion='video-status']", { autoAlpha: 0, x: reduced ? 0 : 18, scale: reduced ? 1 : 0.992, duration: reduced ? 0.18 : 0.55 }, "-=0.42");
      if (!reduced) {
        timeline.to("[data-motion='video-system-label']", { scrambleText: { text: "VIDEO RENDER CONTROL", chars: "01—", speed: 0.6 }, duration: 0.6, ease: "none" }, 0);
        timeline.fromTo(".video-stage__scan", { xPercent: -120 }, { xPercent: 140, duration: 0.85, ease: "power2.inOut" }, 0.08);
      }
    });
    return () => media.revert();
  }, { scope: stageRef });

  return (
    <div className="video-stage" ref={stageRef}>
      <span aria-hidden="true" className="video-stage__scan" />
      <p className="ops-kicker mb-3" data-motion="video-system-label">VIDEO RENDER CONTROL</p>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(390px,0.72fr)]">
      <div data-motion="video-scenes"><SpotlightCard>
        <SectionPanel title="已确认分镜">
          <div className="space-y-4">
            {!canGenerate && generationBlockReason ? <div className="rounded-md border border-amber-500/35 bg-amber-500/8 p-3 text-sm text-amber-100">{generationBlockReason}</div> : null}
            {!task ? <div className="ops-panel-muted p-5"><p className="font-medium">{isRestoringTask ? "正在恢复已有任务" : `准备生成 ${scenes.length} 个分镜`}</p><Button className="mt-4 w-full" disabled={!canGenerate} isLoading={isSubmitting} onClick={onGenerate} type="button"><Film className="h-4 w-4" />开始生成视频</Button></div> : null}
            <div className="grid gap-4">{scenes.map((scene, index) => <StoryboardCard displayIndex={index} key={scene.id} readonly scene={scene} />)}</div>
            {task?.status === "completed" && hasUnsubmittedChanges ? <div className="ops-panel-muted border-amber-500/35 p-4 text-sm text-amber-100">脚本或分镜已修改并重新确认。下方按钮会创建新的视频任务，当前成片仍会保留在项目的成片记录中。</div> : null}
            {task?.status === "completed" && hasUnsubmittedChanges ? <Button className="w-full" disabled={!canGenerate} isLoading={isSubmitting} onClick={onGenerate} type="button"><Film className="h-4 w-4" />按当前修改重新生成视频</Button> : null}
            {task && !running && task.status !== "completed" ? <Button className="w-full" disabled={!canGenerate} isLoading={isSubmitting} onClick={onGenerate} type="button"><Film className="h-4 w-4" />重新提交视频任务</Button> : null}
          </div>
        </SectionPanel>
      </SpotlightCard></div>
      <div data-motion="video-status"><GenerationStatusPanel isCancelling={isCancelling} onCancel={onCancel} task={task} /></div>
      </div>
    </div>
  );
}
