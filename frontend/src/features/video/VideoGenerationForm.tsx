import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { Clapperboard } from "lucide-react";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { SpotlightCard } from "@/components/react-bits/SpotlightCard";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { BGMInfo, TemplateInfo } from "@/types/api";
import { BgmControl } from "@/features/video/BgmControl";
import { LaunchMissionButton } from "@/features/video/LaunchMissionButton";
import { videoFormSchema, type VideoFormValues } from "@/features/video/schema";
import { useToast } from "@/hooks/use-toast";

interface VideoGenerationFormProps {
  bgmFiles: BGMInfo[];
  isRunning: boolean;
  isSubmitting: boolean;
  onSubmit: (values: VideoFormValues) => void;
  templates: TemplateInfo[];
}

function preferredTemplate(templates: TemplateInfo[]) {
  return (
    templates.find((template) => template.key === "1080x1920/video_default.html") ??
    templates.find((template) => template.orientation === "portrait" && template.name.startsWith("video_")) ??
    templates.find((template) => template.size === "1080x1920" && template.orientation === "portrait") ??
    templates.find((template) => template.orientation === "portrait") ??
    templates[0]
  );
}

export function VideoGenerationForm({
  bgmFiles,
  isRunning,
  isSubmitting,
  onSubmit,
  templates,
}: VideoGenerationFormProps) {
  const { toast } = useToast();
  const defaultTemplate = preferredTemplate(templates);
  const defaultBgm = bgmFiles[0];
  const disabled = isSubmitting || isRunning;

  const {
    control,
    formState: { errors },
    handleSubmit,
    register,
    setValue,
    watch,
  } = useForm<VideoFormValues>({
    resolver: zodResolver(videoFormSchema),
    defaultValues: {
      title: "",
      text: "",
      mode: "generate",
      n_scenes: 5,
      frame_template: defaultTemplate?.key ?? "",
      bgm_enabled: false,
      bgm_path: defaultBgm?.path ?? "",
      bgm_volume: 0.3,
    },
  });

  const mode = watch("mode");
  const bgmEnabled = watch("bgm_enabled");

  React.useEffect(() => {
    if (defaultTemplate) {
      setValue("frame_template", defaultTemplate.key, { shouldValidate: true });
    }
  }, [defaultTemplate, setValue]);

  React.useEffect(() => {
    if (defaultBgm) {
      setValue("bgm_path", defaultBgm.path);
    }
  }, [defaultBgm, setValue]);

  return (
    <SpotlightCard>
      <SectionPanel
        className="h-full"
        title="生成设置"
      >
        <form
          className="space-y-5"
          noValidate
          onSubmit={handleSubmit(onSubmit, () => {
            toast({
              title: "任务参数不完整",
              description: "请填写科普选题，并确认画面规格已加载。",
              variant: "destructive",
            });
          })}
        >
          <div className="grid gap-4 lg:grid-cols-[1fr_220px]">
            <div className="space-y-2">
              <label className="control-label" htmlFor="title">
                简报标题
              </label>
              <Input
                disabled={disabled}
                id="title"
                placeholder="可选，留空时由后端自动生成"
                {...register("title")}
              />
              {errors.title ? <p className="text-sm text-destructive">{errors.title.message}</p> : null}
            </div>

            <div className="space-y-2">
              <label className="control-label" htmlFor="mode">
                叙事模式
              </label>
              <Controller
                control={control}
                name="mode"
                render={({ field }) => (
                  <Select disabled={disabled} onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger id="mode">
                      <SelectValue placeholder="选择叙事模式" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="generate">生成分镜</SelectItem>
                      <SelectItem value="fixed">固定脚本</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="control-label" htmlFor="text">
              科普选题 / 脚本输入
            </label>
            <Textarea
              disabled={disabled}
              id="text"
              placeholder="示例：解释有源相控阵雷达如何同时跟踪多个目标，并用 5 个镜头讲清楚。"
              {...register("text")}
            />
            {errors.text ? <p className="text-sm text-destructive">{errors.text.message}</p> : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="control-label" htmlFor="n_scenes">
                分镜数量
              </label>
              <Input
                disabled={disabled || mode === "fixed"}
                id="n_scenes"
                max={20}
                min={1}
                type="number"
                {...register("n_scenes")}
              />
            </div>

            <div className="space-y-2">
              <label className="control-label" htmlFor="frame_template">
                画面规格
              </label>
              <Controller
                control={control}
                name="frame_template"
                render={({ field }) => (
                  <Select disabled={disabled || templates.length === 0} onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger id="frame_template">
                      <SelectValue placeholder="选择画面规格" />
                    </SelectTrigger>
                    <SelectContent>
                      {templates.map((template) => (
                        <SelectItem key={template.key} value={template.key}>
                          {template.size} / {template.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.frame_template ? <p className="text-sm text-destructive">{errors.frame_template.message}</p> : null}
            </div>
          </div>

          <div className="ops-panel-muted p-4">
            <div className="mb-3 flex items-center gap-2">
              <Clapperboard className="h-4 w-4 text-primary" aria-hidden="true" />
              <p className="font-display text-sm font-semibold">声音和背景</p>
            </div>
            <BgmControl
              bgmEnabled={bgmEnabled}
              bgmFiles={bgmFiles}
              control={control}
              disabled={disabled}
              register={register}
            />
          </div>

          <LaunchMissionButton disabled={disabled} isRunning={isRunning} isSubmitting={isSubmitting} />
        </form>
      </SectionPanel>
    </SpotlightCard>
  );
}
