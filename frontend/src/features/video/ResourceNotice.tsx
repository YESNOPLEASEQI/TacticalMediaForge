import { CircleAlert } from "lucide-react";

interface ResourceNoticeProps {
  apiAvailable: boolean;
  errorMessage?: string;
  isLoading: boolean;
  templateCount: number;
}

export function ResourceNotice({ apiAvailable, errorMessage }: ResourceNoticeProps) {
  if (!apiAvailable) {
    return (
      <div className="flex items-start gap-3 rounded-md border border-destructive/45 bg-destructive/10 p-3 text-sm">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
        <div>
          <p className="font-medium text-foreground">生成服务未连接</p>
          <p className="text-muted-foreground">当前仍可编辑内容，恢复连接后再开始生成。</p>
        </div>
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="flex items-start gap-3 rounded-md border border-destructive/45 bg-destructive/10 p-3 text-sm">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
        <div>
          <p className="font-medium text-foreground">资源扫描失败</p>
          <p className="text-muted-foreground">{errorMessage}</p>
        </div>
      </div>
    );
  }

  return null;
}
