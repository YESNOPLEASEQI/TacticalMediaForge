import * as React from "react";
import { Check, Eye, ImagePlus, Layers3, Loader2, Trash2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ReferenceAsset } from "@/types/api";

interface ReferenceAssetLibraryProps {
  assets: ReferenceAsset[];
  disabled?: boolean;
  isLoading?: boolean;
  isUploading?: boolean;
  uploadError?: string;
  usageCounts?: Record<string, number>;
  boundSceneCount?: number;
  onUpload: (file: File) => void;
  onDelete: (assetId: string) => void;
  onApplyAll: (assetIds: string[]) => void;
  onClearAll: () => void;
}

export function ReferenceAssetLibrary({
  assets,
  disabled = false,
  isLoading = false,
  isUploading = false,
  uploadError,
  usageCounts = {},
  boundSceneCount = 0,
  onUpload,
  onDelete,
  onApplyAll,
  onClearAll,
}: ReferenceAssetLibraryProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const wasUploading = React.useRef(false);
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [uploadMessage, setUploadMessage] = React.useState<string | null>(null);

  React.useEffect(() => {
    const available = new Set(assets.map((asset) => asset.id));
    setSelectedIds((current) => current.filter((id) => available.has(id)));
  }, [assets]);

  React.useEffect(() => {
    if (wasUploading.current && !isUploading && !uploadError) {
      setUploadMessage("上传成功，已加入装备视觉参考。");
    }
    if (isUploading) setUploadMessage(null);
    wasUploading.current = isUploading;
  }, [isUploading, uploadError]);

  const toggleSelected = (assetId: string) => {
    setSelectedIds((current) => current.includes(assetId)
      ? current.filter((id) => id !== assetId)
      : current.length < 4 ? [...current, assetId] : current);
  };

  return (
    <section className="ops-panel-muted space-y-3 p-3" aria-labelledby="reference-library-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-medium" id="reference-library-title">装备视觉参考</h3>
          <p className="mt-1 max-w-2xl text-xs text-muted-foreground">
            上传 PNG、JPEG 或 WEBP，供 MiniMax H3 保持装备身份与结构一致。每个分镜最多绑定 4 张，不作为首帧。
          </p>
        </div>
        <input
          accept="image/png,image/jpeg,image/webp"
          className="sr-only"
          disabled={disabled || isUploading}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onUpload(file);
            event.target.value = "";
          }}
          ref={inputRef}
          type="file"
        />
        <Button
          disabled={disabled || isUploading}
          isLoading={isUploading}
          onClick={() => inputRef.current?.click()}
          size="sm"
          type="button"
          variant="secondary"
        >
          <ImagePlus className="h-4 w-4" aria-hidden="true" />
          添加参考图
        </Button>
      </div>

      {uploadError ? <p className="text-sm text-destructive" role="alert">上传失败：{uploadError}</p> : null}
      {uploadMessage ? <p className="text-sm text-emerald-300" role="status">{uploadMessage}</p> : null}
      {selectedIds.length >= 4 ? <p className="text-xs text-amber-200">已达到单个分镜最多 4 张的选择上限。</p> : null}

      {isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />正在读取参考图库…</p>
      ) : assets.length === 0 ? (
        <p className="text-sm text-muted-foreground">尚未上传装备视觉参考。MiniMax H3 仍可在无参考图时运行。</p>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {assets.map((asset) => {
            const selected = selectedIds.includes(asset.id);
            const usageCount = usageCounts[asset.id] ?? 0;
            return (
              <div className={`group overflow-hidden rounded-md border bg-background/40 ${selected ? "border-primary ring-1 ring-primary" : "border-border/70"}`} key={asset.id}>
                <button
                  aria-label={`${selected ? "取消选择" : "选择"} ${asset.filename}`}
                  aria-pressed={selected}
                  className="relative block w-full text-left"
                  disabled={disabled || (!selected && selectedIds.length >= 4)}
                  onClick={() => toggleSelected(asset.id)}
                  type="button"
                >
                  <img alt={asset.filename} className="aspect-video w-full object-cover" loading="lazy" src={asset.url} />
                  {selected ? <span className="absolute right-1.5 top-1.5 rounded-full bg-primary p-1 text-primary-foreground"><Check className="h-3 w-3" /></span> : null}
                </button>
                <div className="space-y-1 p-2">
                  <p className="truncate text-[11px]" title={asset.filename}>{asset.filename}</p>
                  <p className="text-[11px] text-muted-foreground">{asset.width}×{asset.height} · 已用于 {usageCount} 个分镜</p>
                  <div className="flex justify-end gap-1">
                    <Button aria-label={`预览 ${asset.filename}`} className="h-7 w-7 px-0" onClick={() => window.open(asset.url, "_blank", "noopener,noreferrer")} size="icon" type="button" variant="ghost"><Eye className="h-3.5 w-3.5" /></Button>
                    <Button
                      aria-label={`删除 ${asset.filename}`}
                      className="h-7 w-7 px-0"
                      disabled={disabled}
                      onClick={() => {
                        const usage = usageCount > 0 ? `当前有 ${usageCount} 个分镜正在使用；删除后会同时移除这些绑定。` : "当前没有分镜使用它。";
                        if (window.confirm(`删除装备视觉参考“${asset.filename}”？${usage}`)) onDelete(asset.id);
                      }}
                      size="icon"
                      type="button"
                      variant="ghost"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="flex flex-col gap-2 border-t border-border/60 pt-3 sm:flex-row">
        <Button disabled={disabled || selectedIds.length === 0} onClick={() => onApplyAll(selectedIds)} size="sm" type="button" variant="secondary">
          <Layers3 className="h-4 w-4" />将已选参考应用到全部分镜（{selectedIds.length}）
        </Button>
        <Button disabled={disabled || boundSceneCount === 0} onClick={onClearAll} size="sm" type="button" variant="ghost">
          <XCircle className="h-4 w-4" />清除全部分镜绑定
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">清除绑定不会删除图库里的参考图。</p>
    </section>
  );
}
