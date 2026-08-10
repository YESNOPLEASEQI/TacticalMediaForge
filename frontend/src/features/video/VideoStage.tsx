import * as React from "react";
import { ArrowLeft, Film, Settings2 } from "lucide-react";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { SpotlightCard } from "@/components/react-bits/SpotlightCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { BGMInfo, ReferenceAsset, Task, TemplateInfo } from "@/types/api";
import { GenerationStatusPanel } from "@/features/video/GenerationStatusPanel";
import { StoryboardCard } from "@/features/video/StoryboardCard";
import type { EditableStoryboardScene, VideoWorkflowConfig } from "@/features/video/workflow";
import { gsap, useGSAP } from "@/lib/gsap";

interface VideoStageProps {
  scenes: EditableStoryboardScene[];
  task?: Task;
  config: VideoWorkflowConfig;
  templates: TemplateInfo[];
  bgmFiles: BGMInfo[];
  referenceAssets?: ReferenceAsset[];
  referenceMode?: "standard" | "h3";
  isSubmitting: boolean;
  isCancelling: boolean;
  isRestoringTask?: boolean;
  hasUnsubmittedChanges?: boolean;
  onConfigChange: (config: VideoWorkflowConfig) => void;
  onBack: () => void;
  onGenerate: () => void;
  onCancel: () => void;
  canGenerate?: boolean;
  generationBlockReason?: string;
}

export function VideoStage({
  scenes,
  task,
  config,
  templates,
  bgmFiles,
  referenceAssets = [],
  referenceMode = "standard",
  isSubmitting,
  isCancelling,
  isRestoringTask = false,
  hasUnsubmittedChanges = false,
  onConfigChange,
  onBack,
  onGenerate,
  onCancel,
  canGenerate = true,
  generationBlockReason,
}: VideoStageProps) {
  const stageRef = React.useRef<HTMLDivElement>(null);
  const running = task?.status === "pending" || task?.status === "running";
  const completed = task?.status === "completed";
  const totalDuration = scenes.reduce((sum, scene) => sum + scene.estimatedDuration, 0);
  const boundReferenceCount = new Set(scenes.flatMap((scene) => scene.referenceAssetIds ?? [])).size;
  const template = templates.find((item) => item.key === config.frameTemplate);

  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add({ reduceMotion: "(prefers-reduced-motion: reduce)", allowMotion: "(prefers-reduced-motion: no-preference)" }, (context) => {
      const reduced = Boolean(context.conditions?.reduceMotion);
      const timeline = gsap.timeline({ defaults: { ease: "reveal", overwrite: "auto" } });
      timeline
        .from("[data-motion='video-system-label']", { autoAlpha: 0, y: reduced ? 0 : 8, duration: reduced ? 0.16 : 0.35 })
        .from("[data-motion='video-scenes']", { autoAlpha: 0, x: reduced ? 0 : -18, scale: reduced ? 1 : 0.992, duration: reduced ? 0.18 : 0.55 }, "-=0.14")
        .from("[data-motion='video-status']", { autoAlpha: 0, x: reduced ? 0 : 18, scale: reduced ? 1 : 0.992, duration: reduced ? 0.18 : 0.55 }, "-=0.42");
      if (!reduced) timeline.fromTo(".video-stage__scan", { xPercent: -120 }, { xPercent: 140, duration: 0.85, ease: "power2.inOut" }, 0.08);
    });
    return () => media.revert();
  }, { scope: stageRef });

  return (
    <div className="video-stage" ref={stageRef}>
      <span aria-hidden="true" className="video-stage__scan" />
      <p className="ops-kicker mb-3" data-motion="video-system-label">VIDEO RENDER CONTROL</p>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(390px,0.72fr)]">
        <div className="space-y-4" data-motion="video-scenes">
          <SpotlightCard>
            <SectionPanel actions={<Button onClick={onBack} size="sm" type="button" variant="ghost"><ArrowLeft className="h-4 w-4" />返回分镜</Button>} title="生成前确认">
              <div className="space-y-4">
                <dl className="grid gap-3 text-sm sm:grid-cols-2">
                  <div className="ops-panel-muted p-3"><dt className="text-xs text-muted-foreground">视频生成器</dt><dd className="mt-1 font-medium">{referenceMode === "h3" ? "MiniMax H3" : "LTX 2.3"}</dd></div>
                  <div className="ops-panel-muted p-3"><dt className="text-xs text-muted-foreground">分镜与预计时长</dt><dd className="mt-1 font-medium">{scenes.length} 镜 · 约 {totalDuration} 秒</dd></div>
                  {referenceMode === "h3" ? <div className="ops-panel-muted p-3"><dt className="text-xs text-muted-foreground">装备视觉参考</dt><dd className="mt-1 font-medium">{boundReferenceCount} 张 · {scenes.filter((scene) => (scene.referenceAssetIds?.length ?? 0) > 0).length}/{scenes.length} 个分镜已绑定</dd></div> : null}
                  <div className="ops-panel-muted p-3"><dt className="text-xs text-muted-foreground">画面模板</dt><dd className="mt-1 font-medium">{template ? `${template.size} / ${template.display_name || template.name}` : config.frameTemplate}</dd></div>
                  <div className="ops-panel-muted p-3"><dt className="text-xs text-muted-foreground">解说</dt><dd className="mt-1 font-medium">{scenes.filter((scene) => scene.narration.trim()).length}/{scenes.length} 个分镜已就绪</dd></div>
                  <div className="ops-panel-muted p-3"><dt className="text-xs text-muted-foreground">背景音乐</dt><dd className="mt-1 font-medium">{config.bgmEnabled ? (bgmFiles.find((item) => item.path === config.bgmPath)?.name ?? config.bgmPath) : "不使用"}</dd></div>
                </dl>

                <div className="ops-panel-muted space-y-4 p-4">
                  <div className="flex items-center gap-2"><Settings2 className="h-4 w-4 text-primary" /><h3 className="font-medium">输出设置</h3></div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label className="control-label" htmlFor="output-template">画面模板</label>
                      <Select disabled={running || templates.length === 0} value={config.frameTemplate} onValueChange={(frameTemplate) => onConfigChange({ ...config, frameTemplate })}>
                        <SelectTrigger id="output-template"><SelectValue placeholder="选择画面模板" /></SelectTrigger>
                        <SelectContent>{templates.map((item) => <SelectItem key={item.key} value={item.key}>{item.size} / {item.display_name || item.name}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="control-label" htmlFor="output-bgm">背景音乐</label>
                      <Select disabled={running || bgmFiles.length === 0} value={config.bgmEnabled ? config.bgmPath || "none" : "none"} onValueChange={(bgmPath) => onConfigChange({ ...config, bgmEnabled: bgmPath !== "none", bgmPath: bgmPath === "none" ? "" : bgmPath })}>
                        <SelectTrigger id="output-bgm"><SelectValue placeholder="不使用背景音乐" /></SelectTrigger>
                        <SelectContent><SelectItem value="none">不使用背景音乐</SelectItem>{bgmFiles.map((bgm) => <SelectItem key={bgm.path} value={bgm.path}>{bgm.name}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between"><label className="control-label" htmlFor="output-bgm-volume">背景音乐音量</label><span className="font-data text-xs text-muted-foreground">{Math.round(config.bgmVolume * 100)}%</span></div>
                    <Input aria-label="背景音乐音量" disabled={running || !config.bgmEnabled} id="output-bgm-volume" max={1} min={0} onChange={(event) => onConfigChange({ ...config, bgmVolume: Number(event.target.value) })} step={0.05} type="range" value={config.bgmVolume} />
                  </div>
                </div>

                {!canGenerate && generationBlockReason ? <div className="rounded-md border border-amber-500/35 bg-amber-500/8 p-3 text-sm text-amber-100" role="alert">{generationBlockReason}</div> : null}
                {!task ? <div className="ops-panel-muted p-5"><p className="font-medium">{isRestoringTask ? "正在恢复已有任务" : `已准备生成 ${scenes.length} 个分镜`}</p><Button className="mt-4 w-full" disabled={!canGenerate} isLoading={isSubmitting} onClick={onGenerate} type="button"><Film className="h-4 w-4" />开始生成视频</Button></div> : null}
                {completed && hasUnsubmittedChanges ? <div className="ops-panel-muted border-amber-500/35 p-4 text-sm text-amber-100">输出设置或分镜已有修改。生成新版本不会覆盖当前成片，旧结果会保留在项目记录中。</div> : null}
                {completed && hasUnsubmittedChanges ? <Button className="w-full" disabled={!canGenerate} isLoading={isSubmitting} onClick={onGenerate} type="button"><Film className="h-4 w-4" />按当前修改生成新版本</Button> : null}
                {task && !running && !completed ? <Button className="w-full" disabled={!canGenerate} isLoading={isSubmitting} onClick={onGenerate} type="button"><Film className="h-4 w-4" />重新提交视频任务</Button> : null}
              </div>
            </SectionPanel>
          </SpotlightCard>

          <SpotlightCard>
            <SectionPanel actions={<span className="font-data text-xs text-muted-foreground">{scenes.length} 镜</span>} title="已确认分镜">
              <div className="grid gap-4">{scenes.map((scene, index) => <StoryboardCard displayIndex={index} key={scene.id} readonly referenceAssets={referenceAssets} scene={scene} showReferences={referenceMode === "h3"} />)}</div>
            </SectionPanel>
          </SpotlightCard>
        </div>
        <div data-motion="video-status"><GenerationStatusPanel isCancelling={isCancelling} onCancel={onCancel} onEditStoryboard={onBack} onGenerateNewVersion={completed ? onGenerate : undefined} task={task} /></div>
      </div>
    </div>
  );
}
