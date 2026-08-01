import * as React from "react";
import { Clock3, Image, Video } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { containsCjk, normalizeEstimatedDuration, type EditableStoryboardScene } from "@/features/video/workflow";

interface StoryboardCardProps {
  scene: EditableStoryboardScene;
  disabled?: boolean;
  readonly?: boolean;
  displayIndex?: number;
  onChange?: (scene: EditableStoryboardScene) => void;
}

function sceneStatus(scene: EditableStoryboardScene) {
  if (scene.status === "completed") return { label: "已完成", variant: "success" as const };
  if (scene.status === "running") return { label: "生成中", variant: "warning" as const };
  if (scene.status === "failed") return { label: "失败", variant: "destructive" as const };
  return { label: "待生成", variant: "secondary" as const };
}

export function StoryboardCard({ scene, disabled = false, readonly = false, displayIndex, onChange }: StoryboardCardProps) {
  const cardRef = React.useRef<HTMLElement>(null);
  const update = (patch: Partial<EditableStoryboardScene>) => onChange?.({ ...scene, ...patch });
  const status = sceneStatus(scene);
  const locked = readonly;
  const hasChinesePrompt = containsCjk(scene.mediaPrompt);

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
