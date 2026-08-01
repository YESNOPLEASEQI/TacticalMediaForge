import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, RefreshCw } from "lucide-react";
import { deleteSession, historyQueries, retryGenerationJob } from "@/api/history";
import { OperationsShell, StatusStrip, WorkbenchHeader } from "@/components/operations/OperationsShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import type { GenerationJob, HistoryStatus, SessionSummary } from "@/types/history";
import { JobInspector } from "@/features/history/JobInspector";
import { MessageTimeline } from "@/features/history/MessageTimeline";
import { SessionList } from "@/features/history/SessionList";

interface HistoryDashboardProps {
  onOpenGenerator: (sessionId: string | null) => void;
}

function matchesSearch(session: SessionSummary, search: string) {
  if (!search.trim()) {
    return true;
  }

  const needle = search.trim().toLowerCase();
  return [
    session.title,
    session.id,
    session.latest_job_id,
    session.status,
    String(session.metadata.mode ?? ""),
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(needle));
}

function terminalStatus(status: HistoryStatus) {
  return status === "success" || status === "failed" || status === "cancelled";
}

export function HistoryDashboard({ onOpenGenerator }: HistoryDashboardProps) {
  const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);
  const [activeJobId, setActiveJobId] = React.useState<string | null>(null);
  const [search, setSearch] = React.useState("");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const sessionsQuery = useQuery(historyQueries.sessions({ limit: 80 }));
  const sessions = React.useMemo(
    () => (sessionsQuery.data?.sessions ?? []).filter((session) => matchesSearch(session, search)),
    [search, sessionsQuery.data?.sessions],
  );

  React.useEffect(() => {
    if (activeSessionId || sessions.length === 0) {
      return;
    }
    setActiveSessionId(sessions[0].id);
  }, [activeSessionId, sessions]);

  const detailQuery = useQuery(historyQueries.session(activeSessionId));
  const detail = detailQuery.data;
  const activeJob =
    detail?.generation_jobs.find((job) => job.id === activeJobId) ?? detail?.generation_jobs[0] ?? null;

  React.useEffect(() => {
    if (!detail?.generation_jobs.length) {
      setActiveJobId(null);
      return;
    }

    if (!activeJobId || !detail.generation_jobs.some((job) => job.id === activeJobId)) {
      setActiveJobId(detail.generation_jobs[0].id);
    }
  }, [activeJobId, detail?.generation_jobs]);

  const retryMutation = useMutation({
    mutationFn: retryGenerationJob,
    onSuccess: async (response) => {
      await navigator.clipboard.writeText(JSON.stringify(response.params, null, 2));
      toast({ title: "已复制复用参数", description: "可回到生成页粘贴或对照修改。" });
    },
    onError: (error) => {
      toast({
        title: "读取复用参数失败",
        description: error instanceof Error ? error.message : "无法读取该任务的输入参数。",
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSession,
    onSuccess: async () => {
      setActiveSessionId(null);
      setActiveJobId(null);
      await queryClient.invalidateQueries({ queryKey: ["history"] });
      toast({ title: "历史项目已删除" });
    },
    onError: (error) => {
      toast({
        title: "删除失败",
        description: error instanceof Error ? error.message : "无法删除该历史项目。",
        variant: "destructive",
      });
    },
  });

  async function copyJobParams(job: GenerationJob) {
    await navigator.clipboard.writeText(JSON.stringify(job.params, null, 2));
    toast({ title: "参数已复制", description: "包含 Prompt、Workflow、模板和生成配置。" });
  }

  const allSessions = sessionsQuery.data?.sessions ?? [];
  const completedCount = allSessions.filter((session) => terminalStatus(session.status)).length;
  const runningCount = allSessions.filter((session) => session.status === "queued" || session.status === "running").length;

  return (
    <OperationsShell>
      <WorkbenchHeader
        actions={
          <>
            <Button onClick={() => void sessionsQuery.refetch()} size="sm" type="button" variant="secondary">
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              刷新
            </Button>
            <Button onClick={() => onOpenGenerator(null)} size="sm" type="button">
              <DatabaseZap className="h-4 w-4" aria-hidden="true" />
              返回生成
            </Button>
          </>
        }
        eyebrow="历史后台"
        meta={
          <>
            <Badge variant="secondary">Session / Job / Asset</Badge>
            <Badge variant={runningCount > 0 ? "warning" : "outline"}>{runningCount} 个运行中</Badge>
          </>
        }
        summary="按 Session、Message、Generation Job、Asset 和 Workflow Snapshot 查看每次生成，重点服务复现、排错和继续编辑。"
        title="视频生成历史"
      />

      <div className="mb-4">
        <StatusStrip
          items={[
            { label: "历史项目", value: allSessions.length },
            { label: "已归档", tone: "good", value: completedCount },
            { label: "运行中", tone: runningCount > 0 ? "warn" : "default", value: runningCount },
            { label: "当前 Session", value: activeSessionId ? activeSessionId.slice(0, 8) : "未选择" },
          ]}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[310px_minmax(0,1fr)_390px]">
        <SessionList
          activeSessionId={activeSessionId}
          errorMessage={sessionsQuery.error instanceof Error ? sessionsQuery.error.message : undefined}
          isLoading={sessionsQuery.isLoading}
          onSearchChange={setSearch}
          onSelectSession={(sessionId) => {
            setActiveSessionId(sessionId);
            setActiveJobId(null);
          }}
          search={search}
          sessions={sessions}
        />

        <MessageTimeline
          activeJobId={activeJob?.id ?? null}
          jobs={detail?.generation_jobs ?? []}
          messages={detail?.messages ?? []}
          onCopyParams={(job) => void copyJobParams(job)}
          onRetry={(job) => retryMutation.mutate(job.id)}
          onSelectJob={setActiveJobId}
        />

        <div className="space-y-3">
          {activeSessionId ? (
            <Button className="w-full" onClick={() => onOpenGenerator(activeSessionId)} type="button">
              <DatabaseZap className="h-4 w-4" aria-hidden="true" />
              继续编辑当前项目
            </Button>
          ) : null}
          <JobInspector
            assets={detail?.assets ?? []}
            job={activeJob}
            onCopyParams={(job) => void copyJobParams(job)}
            snapshots={detail?.workflow_snapshots ?? []}
          />
          {activeSessionId ? (
            <Button
              className="w-full"
              isLoading={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate(activeSessionId)}
              type="button"
              variant="destructive"
            >
              删除当前历史项目
            </Button>
          ) : null}
          {detailQuery.isError ? (
            <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive-foreground">
              历史详情读取失败。
            </p>
          ) : null}
        </div>
      </div>
    </OperationsShell>
  );
}
