import * as React from "react";
import { Check, Clock3, Image, ImagePlus, Video, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { containsCjk, normalizeEstimatedDuration, type EditableStoryboardScene } from "@/features/video/workflow";
import type { ReferenceAsset } from "@/types/api";

interface StoryboardCardProps {
  scene: EditableStoryboardScene;
  disabled?: boolean;
  readonly?: boolean;
  displayIndex?: number;
  onChange?: (scene: EditableStoryboardScene) => void;
  referenceAssets?: ReferenceAsset[];
  showReferences?: boolean;
}

function sceneStatus(scene: EditableStoryboardScene) {
  if (scene.status === "completed") return { label: "已完成", variant: "success" as const };
  if (scene.status === "running") return { label: "生成中", variant: "warning" as const };
  if (scene.status === "failed") return { label: "失败", variant: "destructive" as const };
  return { label: "待生成", variant: "secondary" as const };
}

export function StoryboardCard({ scene, disabled = false, readonly = false, displayIndex, onChange, referenceAssets = [], showReferences = false }: StoryboardCardProps) {
  const cardRef = React.useRef<HTMLElement>(null);
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const update = (patch: Partial<EditableStoryboardScene>) => onChange?.({ ...scene, ...patch });
  const status = sceneStatus(scene);
  const locked = readonly;
  const hasChinesePrompt = containsCjk(scene.mediaPrompt);
  const selectedReferenceIds = scene.referenceAssetIds ?? [];
  const selectedAssets = referenceAssets.filter((asset) => selectedReferenceIds.includes(asset.id));

  const toggleReference = (assetId: string) => {
    const next = selectedReferenceIds.includes(assetId)
      ? selectedReferenceIds.filter((id) => id !== assetId)
      : selectedReferenceIds.length < 4
        ? [...selectedReferenceIds, assetId]
        : selectedReferenceIds;
    update({ referenceAssetIds: next });
  };

  return (
    <article className="storyboard-card" data-scene-id={scene.id} data-status={scene.status} ref={cardRef}>
      <span aria-hidden="true" className="storyboard-card__scan" />
      <header className="storyboard-card__header flex-wrap gap-2">
        <span className="font-data text-xs text-primary">SHOT {String((displayIndex ?? scene.index) + 1).padStart(2, "0")}</span>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
          <Badge variant={status.variant}>{status.label}</Badge>
          <Badge variant="secondary">{scene.assetType === "video" ? "视频" : "图片"}</Badge>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
            {scene.estimatedDuration} 秒
          </span>
        </div>
      </header>

      <div className="space-y-3 p-3">
        <div className="space-y-1.5">
          <label className="control-label" htmlFor={`${scene.id}-narration`}>对应解说词</label>
          <Textarea className="min-h-[76px] resize-y py-2" id={`${scene.id}-narration`} disabled={disabled || locked} value={scene.narration} onChange={(event) => update({ narration: event.target.value })} />
        </div>
        <div className="space-y-1.5">
          <label className="control-label" htmlFor={`${scene.id}-prompt`}>英文生成提示词</label>
          <Textarea
            aria-describedby={`${scene.id}-prompt-help`}
            aria-invalid={hasChinesePrompt}
            className="min-h-[112px] resize-y py-2 font-data text-xs leading-5"
            id={`${scene.id}-prompt`}
            disabled={disabled || locked}
            value={scene.mediaPrompt}
            onChange={(event) => update({ mediaPrompt: event.target.value, visualDescription: event.target.value })}
          />
          <p className="text-xs text-muted-foreground" id={`${scene.id}-prompt-help`}>直接用于图片或视频生成，仅允许英文。</p>
          {hasChinesePrompt ? <p className="text-xs text-destructive" role="alert">提示词包含中文，无法确认或提交。</p> : null}
        </div>

        {showReferences && !locked ? (
          <div className="space-y-2 rounded-md border border-border/60 bg-background/30 p-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="control-label">装备视觉参考</p>
                <p className="text-xs text-muted-foreground">用于保持装备身份与结构一致，不作为首帧（已选 {selectedReferenceIds.length}/4）。</p>
              </div>
              <Button
                aria-expanded={pickerOpen}
                disabled={disabled || referenceAssets.length === 0}
                onClick={() => setPickerOpen((open) => !open)}
                size="sm"
                type="button"
                variant="secondary"
              >
                <ImagePlus className="h-4 w-4" aria-hidden="true" />
                {pickerOpen ? "收起" : "+ 选择"}
              </Button>
            </div>
            {selectedAssets.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {selectedAssets.map((asset) => (
                  <button
                    aria-label={`从当前分镜移除 ${asset.filename}`}
                    className="group relative overflow-hidden rounded border border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    key={asset.id}
                    onClick={() => toggleReference(asset.id)}
                    type="button"
                  >
                    <img alt={asset.filename} className="h-12 w-16 object-cover" src={asset.url} />
                    <span className="absolute inset-0 hidden items-center justify-center bg-background/75 group-hover:flex"><X className="h-4 w-4" /></span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">当前分镜未绑定装备视觉参考。</p>
            )}
            {pickerOpen ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label="可用装备视觉参考">
                {referenceAssets.map((asset) => {
                  const selected = selectedReferenceIds.includes(asset.id);
                  const atLimit = !selected && selectedReferenceIds.length >= 4;
                  return (
                    <button
                      aria-pressed={selected}
                      className={`relative overflow-hidden rounded border text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${selected ? "border-primary ring-1 ring-primary" : "border-border/70"}`}
                      disabled={disabled || atLimit}
                      key={asset.id}
                      onClick={() => toggleReference(asset.id)}
                      type="button"
                    >
                      <img alt={asset.filename} className="aspect-video w-full object-cover" src={asset.url} />
                      <span className="flex items-center gap-1 truncate p-1 text-[11px] text-muted-foreground">
                        {selected ? <Check className="h-3 w-3 text-primary" /> : null}{asset.filename}
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : null}
            {selectedReferenceIds.length >= 4 ? (
              <p className="text-xs text-amber-200" role="status">已达到每镜 4 张参考图上限。</p>
            ) : null}
          </div>
        ) : showReferences && selectedAssets.length > 0 ? (
          <div className="space-y-2 rounded-md border border-border/60 bg-background/30 p-2.5">
            <p className="control-label">装备视觉参考（{selectedAssets.length}）</p>
            <div className="flex flex-wrap gap-2">
              {selectedAssets.map((asset) => <img alt={asset.filename} className="h-12 w-16 rounded border border-border/70 object-cover" key={asset.id} src={asset.url} />)}
            </div>
          </div>
        ) : null}

        {!locked ? (
          <div className="grid grid-cols-2 gap-3 rounded-md border border-border/60 bg-background/30 p-2.5">
            <div className="space-y-1.5">
              <label className="control-label" htmlFor={`${scene.id}-duration`}>预计时长</label>
              <Input className="h-9" id={`${scene.id}-duration`} disabled={disabled} min={1} step={1} type="number" value={scene.estimatedDuration} onChange={(event) => update({ estimatedDuration: normalizeEstimatedDuration(Number(event.target.value)) })} />
            </div>
            <div className="space-y-1.5">
              <label className="control-label">资产类型</label>
              <Select disabled={disabled} value={scene.assetType} onValueChange={(assetType: "image" | "video") => update({ assetType })}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="video"><Video className="mr-2 inline h-4 w-4" />视频</SelectItem>
                  <SelectItem value="image"><Image className="mr-2 inline h-4 w-4" />图片</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        ) : null}

      </div>
    </article>
  );
}
