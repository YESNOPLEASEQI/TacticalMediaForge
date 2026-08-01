import { Controller, type Control, type UseFormRegister } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { BGMInfo } from "@/types/api";
import type { VideoFormValues } from "@/features/video/schema";

interface BgmControlProps {
  bgmFiles: BGMInfo[];
  bgmEnabled: boolean;
  control: Control<VideoFormValues>;
  disabled: boolean;
  register: UseFormRegister<VideoFormValues>;
}

export function BgmControl({ bgmFiles, bgmEnabled, control, disabled, register }: BgmControlProps) {
  return (
    <div className="rounded-md border border-border bg-secondary/45 p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <label className="control-label" htmlFor="bgm_enabled">
            背景音频
          </label>
        </div>
        <Controller
          control={control}
          name="bgm_enabled"
          render={({ field }) => (
            <Switch
              id="bgm_enabled"
              checked={field.value}
              disabled={disabled || bgmFiles.length === 0}
              onCheckedChange={field.onChange}
            />
          )}
        />
      </div>
      {bgmEnabled && (
        <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_120px]">
          <Controller
            control={control}
            name="bgm_path"
            render={({ field }) => (
              <Select disabled={disabled} onValueChange={field.onChange} value={field.value}>
                <SelectTrigger aria-label="选择背景音频">
                  <SelectValue placeholder="选择 BGM" />
                </SelectTrigger>
                <SelectContent>
                  {bgmFiles.map((bgm) => (
                    <SelectItem key={bgm.path} value={bgm.path}>
                      {bgm.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          <Input
            aria-label="背景音频音量"
            type="number"
            min={0}
            max={1}
            step={0.1}
            disabled={disabled}
            {...register("bgm_volume")}
          />
        </div>
      )}
    </div>
  );
}
