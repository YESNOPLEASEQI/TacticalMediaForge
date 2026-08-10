import * as React from "react";
import { ImagePlus, Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ReferenceAsset } from "@/types/api";

interface ReferenceAssetLibraryProps {
  assets: ReferenceAsset[];
  disabled?: boolean;
  isLoading?: boolean;
  isUploading?: boolean;
  uploadError?: string;
  onUpload: (file: File) => void;
  onDelete: (assetId: string) => void;
}

export function ReferenceAssetLibrary({
  assets,
  disabled = false,
  isLoading = false,
  isUploading = false,
  uploadError,
  onUpload,
  onDelete,
}: ReferenceAssetLibraryProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);

  return (
    <section className="ops-panel-muted space-y-3 p-3" aria-labelledby="reference-library-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-medium" id="reference-library-title">MiniMax H3 equipment references</h3>
          <p className="text-xs text-muted-foreground">
            Upload PNG, JPEG, or WEBP images. Bind up to 4 images per shot for identity and structure.
          </p>
        </div>
        <>
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
            Add reference
          </Button>
        </>
      </div>
      {uploadError ? <p className="text-sm text-destructive" role="alert">{uploadError}</p> : null}
      {isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading references…</p>
      ) : assets.length === 0 ? (
        <p className="text-sm text-muted-foreground">No equipment references uploaded yet. H3 can still run without one.</p>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {assets.map((asset) => (
            <div className="group relative overflow-hidden rounded-md border border-border/70 bg-background/40" key={asset.id}>
              <img alt={asset.filename} className="aspect-video w-full object-cover" loading="lazy" src={asset.url} />
              <div className="flex items-center justify-between gap-1 p-1.5">
                <span className="truncate text-[11px] text-muted-foreground" title={asset.filename}>{asset.filename}</span>
                <Button
                  aria-label={`Delete ${asset.filename}`}
                  className="h-7 w-7 shrink-0 px-0"
                  disabled={disabled}
                  onClick={() => {
                    if (window.confirm(`Delete ${asset.filename}?`)) onDelete(asset.id);
                  }}
                  size="icon"
                  type="button"
                  variant="ghost"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
