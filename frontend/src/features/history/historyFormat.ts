import type { HistoryStatus } from "@/types/history";

export function formatDateTime(value?: string | null) {
  if (!value) {
    return "未记录";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatDuration(value?: number | null) {
  if (!value) {
    return "0s";
  }

  if (value < 60) {
    return `${value.toFixed(1)}s`;
  }

  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return `${minutes}m ${seconds}s`;
}

export function formatBytes(value?: number | null) {
  if (!value) {
    return "0 MB";
  }

  const mb = value / 1024 / 1024;
  return `${mb.toFixed(mb >= 10 ? 0 : 1)} MB`;
}

export function statusLabel(status: HistoryStatus) {
  const labels: Record<HistoryStatus, string> = {
    queued: "排队中",
    running: "生成中",
    success: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return labels[status];
}

export function statusVariant(status: HistoryStatus) {
  if (status === "success") {
    return "success" as const;
  }
  if (status === "queued" || status === "running") {
    return "warning" as const;
  }
  if (status === "failed" || status === "cancelled") {
    return "destructive" as const;
  }
  return "secondary" as const;
}
