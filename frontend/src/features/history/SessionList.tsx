import { Clock, Film, Search } from "lucide-react";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { ElectricBorder } from "@/components/ElectricBorder";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { SessionSummary } from "@/types/history";
import { formatDateTime, statusLabel, statusVariant } from "@/features/history/historyFormat";

interface SessionListProps {
  activeSessionId: string | null;
  errorMessage?: string;
  isLoading: boolean;
  onSearchChange: (value: string) => void;
  onSelectSession: (sessionId: string) => void;
  search: string;
  sessions: SessionSummary[];
}

export function SessionList({
  activeSessionId,
  errorMessage,
  isLoading,
  onSearchChange,
  onSelectSession,
  search,
  sessions,
}: SessionListProps) {
  return (
    <SectionPanel className="min-h-[calc(100vh-13rem)]" description="按标题、Task ID 或状态定位历史项目。" eyebrow="Sessions" title="项目索引">
      <label className="relative mb-4 block">
        <span className="sr-only">搜索历史项目</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索标题、Task ID、状态"
          type="search"
          value={search}
        />
      </label>

      <div className="space-y-2">
        {isLoading ? (
          <p className="ops-panel-muted p-3 text-sm text-muted-foreground">正在读取历史索引。</p>
        ) : null}

        {errorMessage ? (
          <p className="rounded-md border border-destructive/45 bg-destructive/10 p-3 text-sm text-destructive-foreground">
            历史索引读取失败：{errorMessage}
          </p>
        ) : null}

        {!isLoading && !errorMessage && sessions.length === 0 ? (
          <p className="ops-panel-muted p-3 text-sm text-muted-foreground">
            还没有可展示的历史项目。完成一次生成后会自动出现在这里。
          </p>
        ) : null}

        {sessions.map((session, index) => {
          const isActive = session.id === activeSessionId;
          return (
            <ElectricBorder active={isActive} key={session.id}>
              <button
                className={cn(
                  "w-full rounded-md border border-border/70 bg-background/38 p-3 text-left transition hover:border-primary/45",
                  isActive && "border-primary/70 bg-primary/10",
                )}
                onClick={() => onSelectSession(session.id)}
                type="button"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-sm font-semibold leading-5">{session.title}</p>
                    <p className="mt-1 font-data text-[11px] text-muted-foreground">
                      {String(index + 1).padStart(2, "0")} · {session.latest_job_id?.slice(0, 8)}
                    </p>
                  </div>
                  <Badge variant={statusVariant(session.status)}>{statusLabel(session.status)}</Badge>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                    {formatDateTime(session.updated_at)}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Film className="h-3.5 w-3.5" aria-hidden="true" />
                    {String(session.metadata.n_frames ?? 0)} 镜头
                  </span>
                </div>
              </button>
            </ElectricBorder>
          );
        })}
      </div>
    </SectionPanel>
  );
}
