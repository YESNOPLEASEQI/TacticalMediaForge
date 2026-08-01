import { z } from "zod";

export const videoFormSchema = z.object({
  title: z.string().max(120, "标题最多 120 个字符").optional(),
  text: z.string().min(1, "请输入科普选题或脚本").max(8000, "内容最多 8000 个字符"),
  mode: z.enum(["generate", "fixed"]),
  n_scenes: z.coerce.number().int().min(1).max(20),
  frame_template: z.string().min(1, "请选择画面规格"),
  bgm_enabled: z.boolean(),
  bgm_path: z.string().optional(),
  bgm_volume: z.coerce.number().min(0).max(1),
});

export type VideoFormValues = z.infer<typeof videoFormSchema>;
