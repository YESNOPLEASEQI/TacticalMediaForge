import * as React from "react";
import { CheckCircle2, Info, WandSparkles } from "lucide-react";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { SpotlightCard } from "@/components/react-bits/SpotlightCard";
import { Button } from "@/components/ui/button";
import { ResearchModeSelector } from "@/features/video/ResearchModeSelector";
import { ReferenceAssetLibrary } from "@/features/video/ReferenceAssetLibrary";
import { StoryboardCard } from "@/features/video/StoryboardCard";
import type {
  EditableStoryboardScene,
  WorkflowResearchState,
} from "@/features/video/workflow";
import {
  containsCjk,
  hasDuplicateStoryboardPrompts,
  isUnanchoredStoryboardPrompt,
} from "@/features/video/workflow";
import { researchWarningLabel } from "@/features/video/researchWarnings";
import { gsap, useGSAP } from "@/lib/gsap";
import { newIds } from "@/lib/motionState";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ReferenceAsset } from "@/types/api";

interface StoryboardStageProps {
  projectId?: string;
  scenes: EditableStoryboardScene[];
  disabled: boolean;
  isGenerating: boolean;
  onGenerate: () => void;
  onChange: (scenes: EditableStoryboardScene[]) => void;
  onConfirm: () => void;
  research: WorkflowResearchState;
  researchCapabilityEnabled: boolean;
  onModeChange: (mode: "verified" | "quick") => void;
  referenceMode?: "standard" | "h3";
  onReferenceModeChange?: (mode: "standard" | "h3") => void;
  referenceAssets?: ReferenceAsset[];
  referenceAssetsLoading?: boolean;
  referenceAssetsUploading?: boolean;
  referenceAssetsError?: string;
  onUploadReference?: (file: File) => void;
  onDeleteReference?: (assetId: string) => void;
}

export function StoryboardStage({
  projectId,
  scenes,
  disabled,
  isGenerating,
  onGenerate,
  onChange,
  onConfirm,
  research,
  researchCapabilityEnabled,
  onModeChange,
  referenceMode = "standard",
  onReferenceModeChange,
  referenceAssets: referenceAssetsProp = [],
  referenceAssetsLoading = false,
  referenceAssetsUploading = false,
  referenceAssetsError,
  onUploadReference,
  onDeleteReference,
}: StoryboardStageProps) {
  const stageRef = React.useRef<HTMLDivElement>(null);
  const [engineNotice, setEngineNotice] = React.useState<string | null>(null);
  const seenSceneIds = React.useRef(new Set<string>());
  const hasDuplicatePrompts = hasDuplicateStoryboardPrompts(scenes);
  const referenceAssets = referenceAssetsProp;
  const complete = scenes.length > 0 && !hasDuplicatePrompts && scenes.every(
    (scene) => (
      scene.narration.trim() &&
      scene.mediaPrompt.trim() &&
      (scene.referenceAssetIds?.length ?? 0) <= 4 &&
      !containsCjk(scene.mediaPrompt) &&
      !isUnanchoredStoryboardPrompt(scene.mediaPrompt)
    ),
  );
  const hasUnanchoredPrompt = scenes.some(
    (scene) => isUnanchoredStoryboardPrompt(scene.mediaPrompt),
  );
  const sceneKey = scenes.map((scene) => scene.id).join("|");
  const assetKey = referenceAssets.map((asset) => asset.id).join("|");
  const usageCounts = React.useMemo(() => Object.fromEntries(referenceAssets.map((asset) => [
    asset.id,
    scenes.filter((scene) => (scene.referenceAssetIds ?? []).includes(asset.id)).length,
  ])), [referenceAssets, scenes]);
  const boundSceneCount = scenes.filter((scene) => (scene.referenceAssetIds?.length ?? 0) > 0).length;
  const referenceMessage = research.status === "researching"
    ? "正在获取联网事实资料并生成分镜…"
    : research.status === "reference_unavailable" && Boolean(research.activeJobId) && research.warnings.length > 0
      ? "联网事实增强暂不可用，本次已按快速模式生成。"
      : research.status === "partial_reference"
        ? `部分联网资料不可用，已使用现有参考继续生成（${research.sourceCount} 个来源）`
        : research.status === "reference_ready"
          ? `已使用联网事实增强生成内容（${research.sourceCount} 个来源）`
          : null;
  const confirmationReason = React.useMemo(() => {
    if (scenes.length === 0) return "请先生成至少一个分镜。";
    if (hasDuplicatePrompts) return "存在重复的英文生成提示词，请分别编辑后再确认。";
    const incompleteIndex = scenes.findIndex((scene) => !scene.narration.trim() || !scene.mediaPrompt.trim());
    if (incompleteIndex >= 0) return `SHOT ${String(incompleteIndex + 1).padStart(2, "0")} 缺少解说词或英文生成提示词。`;
    const chineseIndex = scenes.findIndex((scene) => containsCjk(scene.mediaPrompt));
    if (chineseIndex >= 0) return `SHOT ${String(chineseIndex + 1).padStart(2, "0")} 的生成提示词包含中文。`;
    const unanchoredIndex = scenes.findIndex((scene) => isUnanchoredStoryboardPrompt(scene.mediaPrompt));
    if (unanchoredIndex >= 0) return `SHOT ${String(unanchoredIndex + 1).padStart(2, "0")} 的生成提示词没有写明具体主体。`;
    const overLimitIndex = scenes.findIndex((scene) => (scene.referenceAssetIds?.length ?? 0) > 4);
    if (overLimitIndex >= 0) return `SHOT ${String(overLimitIndex + 1).padStart(2, "0")} 超过每镜 4 张参考图上限。`;
    return null;
  }, [hasDuplicatePrompts, scenes]);

  useGSAP(() => {
    const enteringIds = newIds(seenSceneIds.current, scenes.map((scene) => scene.id));
    scenes.forEach((scene) => seenSceneIds.current.add(scene.id));
    if (!enteringIds.length) return;
    const targets = enteringIds.flatMap((id) => Array.from(
      stageRef.current?.querySelectorAll<HTMLElement>(
        `[data-scene-id='${CSS.escape(id)}']`,
      ) ?? [],
    ));
    if (!targets.length) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    gsap.fromTo(
      targets,
      { autoAlpha: 0, y: reduced ? 0 : 24, scale: reduced ? 1 : 0.982 },
      { autoAlpha: 1, y: 0, scale: 1, duration: reduced ? 0.18 : 0.58, stagger: reduced ? 0 : 0.085, ease: "reveal", overwrite: "auto" },
    );
  }, { scope: stageRef, dependencies: [sceneKey], revertOnUpdate: true });

  React.useEffect(() => {
    const available = new Set(referenceAssets.map((asset) => asset.id));
    const sanitized = scenes.map((scene) => {
      const nextIds = (scene.referenceAssetIds ?? []).filter((id) => available.has(id));
      return nextIds.length === (scene.referenceAssetIds ?? []).length
        ? scene
        : { ...scene, referenceAssetIds: nextIds };
    });
    if (sanitized.some((scene, index) => scene !== scenes[index])) onChange(sanitized);
  }, [assetKey, onChange, referenceAssets, scenes]);

  return (
    <div ref={stageRef}>
      <SpotlightCard>
        <SectionPanel
          actions={<span className="font-data text-xs text-muted-foreground">{scenes.length} 镜</span>}
          title="分镜规划"
        >
          <div className="space-y-5">
            <div className="space-y-2">
              <p className="control-label">分镜生成依据</p>
              <ResearchModeSelector
                capabilityEnabled={researchCapabilityEnabled}
                disabled={disabled}
                mode={research.mode}
                onChange={onModeChange}
              />
            </div>
            <div className="ops-panel-muted space-y-2 p-3">
              <label className="control-label" htmlFor="reference-mode">视频生成器</label>
              <Select disabled={disabled} value={referenceMode} onValueChange={(value: "standard" | "h3") => {
                if (referenceMode === "h3" && value === "standard" && boundSceneCount > 0) {
                  setEngineNotice(`已切换到 LTX 2.3，${boundSceneCount} 个分镜的装备视觉参考绑定已保留；切回 MiniMax H3 后会自动恢复。`);
                } else if (referenceMode === "standard" && value === "h3" && boundSceneCount > 0) {
                  setEngineNotice(`已恢复 ${boundSceneCount} 个分镜的装备视觉参考绑定。`);
                } else {
                  setEngineNotice(null);
                }
                onReferenceModeChange?.(value);
              }}>
                <SelectTrigger id="reference-mode"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="standard">LTX 2.3</SelectItem>
                  <SelectItem value="h3">MiniMax H3</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">LTX 2.3 使用文字提示生成；MiniMax H3 可额外绑定装备视觉参考。</p>
            </div>
            {engineNotice ? <div className="flex gap-2 rounded-md border border-primary/30 bg-primary/8 px-3 py-2 text-sm text-muted-foreground" role="status"><Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{engineNotice}</div> : null}
            {referenceMode === "h3" ? (
              <ReferenceAssetLibrary
                assets={referenceAssets}
                boundSceneCount={boundSceneCount}
                disabled={disabled}
                isLoading={referenceAssetsLoading}
                isUploading={referenceAssetsUploading}
                onApplyAll={(assetIds) => onChange(scenes.map((scene) => ({ ...scene, referenceAssetIds: [...assetIds] })))}
                onClearAll={() => onChange(scenes.map((scene) => ({ ...scene, referenceAssetIds: [] })))}
                onDelete={(assetId) => onDeleteReference?.(assetId)}
                onUpload={(file) => onUploadReference?.(file)}
                uploadError={referenceAssetsError}
                usageCounts={usageCounts}
              />
            ) : null}
            {referenceMessage ? (
              <div className="rounded-md border border-border/70 bg-background/35 px-3 py-2 text-sm text-muted-foreground">
                <p role="status">{referenceMessage}</p>
                {research.sources.length || research.warnings.length ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer">查看参考来源与提示</summary>
                    {research.sources.length ? (
                      <ul className="mt-2 space-y-1">
                        {research.sources.map((source) => (
                          <li key={source.url}>
                            <a className="underline underline-offset-2" href={source.url} rel="noreferrer" target="_blank">
                              {source.title}
                            </a>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {research.warnings.length ? (
                      <ul className="mt-2 list-disc space-y-1 pl-5">
                        {research.warnings.map((warning) => (
                          <li key={warning}>{researchWarningLabel(warning)}</li>
                        ))}
                      </ul>
                    ) : null}
                  </details>
                ) : null}
              </div>
            ) : null}
            {scenes.length === 0 ? (
              <div className="ops-panel-muted flex min-h-48 flex-col items-center justify-center gap-3 p-6 text-center">
                <WandSparkles className="h-7 w-7 text-primary" />
                <p className="font-medium">脚本已就绪</p>
                <Button disabled={disabled} isLoading={isGenerating} onClick={onGenerate} type="button"><WandSparkles className="h-4 w-4" />{research.mode === "verified" ? "联网事实增强生成分镜" : "快速生成分镜"}</Button>
              </div>
            ) : (
              <>
                <div className="grid gap-4 xl:grid-cols-2">
                  {scenes.map((scene, index) => (
                    <StoryboardCard
                      disabled={disabled}
                      displayIndex={index}
                      key={scene.id}
                      onChange={(next) => onChange(scenes.map((item, position) => position === index ? next : item))}
                      referenceAssets={referenceAssets}
                      scene={scene}
                      showReferences={referenceMode === "h3"}
                    />
                  ))}
                </div>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Button disabled={disabled} isLoading={isGenerating} onClick={onGenerate} type="button" variant="secondary"><WandSparkles className="h-4 w-4" />{research.mode === "verified" ? "重新使用联网事实增强生成" : "重新生成分镜草稿"}</Button>
                  <Button className="flex-1" disabled={disabled || !complete} onClick={onConfirm} type="button"><CheckCircle2 className="h-4 w-4" />确认分镜，进入视频生成</Button>
                </div>
                {hasUnanchoredPrompt ? (
                  <p className="text-sm text-destructive" role="alert">
                    部分旧分镜提示词没有写明具体主体，请重新生成或编辑后再确认。
                  </p>
                ) : null}
                {hasDuplicatePrompts ? (
                  <p className="text-sm text-destructive" role="alert">
                    部分分镜使用了相同提示词，请重新生成或分别编辑后再确认。
                  </p>
                ) : null}
                {!complete && !hasUnanchoredPrompt && !hasDuplicatePrompts && confirmationReason ? (
                  <p className="text-sm text-amber-200" role="status">确认按钮暂不可用：{confirmationReason}</p>
                ) : null}
              </>
            )}
          </div>
        </SectionPanel>
      </SpotlightCard>
    </div>
  );
}
