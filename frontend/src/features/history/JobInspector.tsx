import { Copy, Download, FileJson, ShieldAlert } from "lucide-react";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { ClickSpark } from "@/components/react-bits/ClickSpark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { GenerationJob, HistoryAsset, WorkflowSnapshot } from "@/types/history";
import {
  formatBytes,
  formatDateTime,
  formatDuration,
  statusLabel,
  statusVariant,
} from "@/features/history/historyFormat";

interface JobInspectorProps {
  assets: HistoryAsset[];
  job: GenerationJob | null;
  onCopyParams: (job: GenerationJob) => void;
  snapshots: WorkflowSnapshot[];
}

function getVideoUrl(job: GenerationJob | null, assets: HistoryAsset[]) {
  const resultUrl = job?.result.video_url;
  if (typeof resultUrl === "string" && resultUrl.length > 0) {
    return resultUrl;
  }

  return assets.find((asset) => asset.asset_type === "video")?.url ?? null;
}

function compactJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

export function JobInspector({ assets, job, onCopyParams, snapshots }: JobInspectorProps) {
  const videoUrl = getVideoUrl(job, assets);
  const snapshot = job ? snapshots.find((item) => item.job_id === job.id) ?? snapshots[0] : null;

  if (!job) {
    return (
      <SectionPanel className="min-h-[calc(100vh-13rem)]" description="选择一个历史项目后查看视频、参数、资产和 Workflow 快照。" eyebrow="Inspector" title="任务检查器">
        <p className="ops-panel-muted p-3 text-sm text-muted-foreground">尚未选择 Job。</p>
      </SectionPanel>
    );
  }

  return (
    <SectionPanel
      actions={<Badge variant={statusVariant(job.status)}>{statusLabel(job.status)}</Badge>}
      className="min-h-[calc(100vh-13rem)]"
      description="检查结果文件和复现参数。"
      eyebrow="Inspector"
      title="任务检查器"
    >
      <div className="space-y-4">
        <section className="overflow-hidden rounded-md border border-border/70 bg-[#11120f]">
          {videoUrl ? (
            <video className="aspect-video w-full bg-[#11120f]" controls preload="metadata" src={videoUrl}>
              <track kind="captions" />
            </video>
          ) : (
            <div className="flex aspect-video items-center justify-center text-sm text-muted-foreground">
              暂无可播放视频。
            </div>
          )}
        </section>

        <section className="ops-panel-muted p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">生成参数</h3>
            <ClickSpark>
              <Button onClick={() => onCopyParams(job)} size="sm" type="button" variant="secondary">
                <Copy className="h-4 w-4" aria-hidden="true" />
                复制
              </Button>
            </ClickSpark>
          </div>

          <dl className="grid grid-cols-2 gap-3 text-xs text-muted-foreground">
            <div>
              <dt className="text-foreground">Job ID</dt>
              <dd className="break-all font-data">{job.id}</dd>
            </div>
            <div>
              <dt className="text-foreground">Provider</dt>
              <dd>{job.provider}</dd>
            </div>
            <div>
              <dt className="text-foreground">模型</dt>
              <dd>{job.model_name ?? "-"}</dd>
            </div>
            <div>
              <dt className="text-foreground">Workflow</dt>
              <dd className="break-all">{job.workflow_id ?? "-"}</dd>
            </div>
            <div>
              <dt className="text-foreground">时长</dt>
              <dd>{formatDuration(job.duration)}</dd>
            </div>
            <div>
              <dt className="text-foreground">完成时间</dt>
              <dd>{formatDateTime(job.completed_at)}</dd>
            </div>
          </dl>

          {job.error_message ? (
            <p className="mt-3 flex gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-xs text-destructive-foreground">
              <ShieldAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
              {job.error_message}
            </p>
          ) : null}
        </section>

        <section className="ops-panel-muted p-4">
          <h3 className="mb-3 text-sm font-semibold">生成资产</h3>
          <div className="space-y-2">
            {assets.length === 0 ? <p className="text-sm text-muted-foreground">暂无资产记录。</p> : null}
            {assets.slice(0, 8).map((asset) => (
              <div className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-background/36 p-2" key={asset.id}>
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium">{asset.filename ?? asset.asset_type}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {asset.asset_type} / {formatBytes(asset.size_bytes)}
                  </p>
                </div>
                {asset.url ? (
                  <Button asChild size="sm" type="button" variant="ghost">
                    <a href={asset.url} rel="noreferrer" target="_blank">
                      <Download className="h-4 w-4" aria-hidden="true" />
                      打开
                    </a>
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        </section>

        <section className="ops-panel-muted p-4">
          <div className="mb-3 flex items-center gap-2">
            <FileJson className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Workflow Snapshot</h3>
          </div>
          <p className="mb-3 break-all text-xs text-muted-foreground">
            {snapshot?.workflow_name ?? "未记录工作流名称"}
          </p>
          <pre className="max-h-72 overflow-auto rounded-md border border-border/60 bg-background/62 p-3 font-data text-[11px] leading-5 text-muted-foreground">
            {compactJson(
              snapshot?.workflow_json && Object.keys(snapshot.workflow_json).length > 0
                ? snapshot.workflow_json
                : snapshot?.ui_json,
            )}
          </pre>
        </section>
      </div>
    </SectionPanel>
  );
}
