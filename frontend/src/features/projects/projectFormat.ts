import type { HistoryStatus } from "@/types/history";

export function formatProjectDate(value?: string | null) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function projectStatusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "草稿",
    active: "创作中",
    completed: "已完成",
    archived: "已归档",
    failed: "需处理",
  };
  return labels[status] ?? status;
}

export function projectStatusVariant(status: string) {
  if (status === "completed") return "success" as const;
  if (status === "active") return "warning" as const;
  if (status === "failed") return "destructive" as const;
  return "secondary" as const;
}

export function projectStageLabel(stage?: string | null) {
  const labels: Record<string, string> = {
    script: "脚本",
    storyboard: "分镜",
    video: "视频生成",
    output: "成片",
  };
  return stage ? labels[stage] ?? stage : "待开始";
}

export function jobStatusLabel(status?: HistoryStatus | null) {
  if (!status) return "尚未生成";
  const labels: Record<HistoryStatus, string> = {
    queued: "排队中",
    running: "生成中",
    success: "生成完成",
    failed: "生成失败",
    cancelled: "已取消",
  };
  return labels[status];
}
