import { Copy, RotateCcw, Workflow } from "lucide-react";
import { ClickSpark } from "@/components/react-bits/ClickSpark";
import { ElectricBorder } from "@/components/ElectricBorder";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { GenerationJob } from "@/types/history";
import { formatDuration, statusLabel, statusVariant } from "@/features/history/historyFormat";

interface GenerationCardProps {
  active: boolean;
  job: GenerationJob;
  onCopyParams: (job: GenerationJob) => void;
  onRetry: (job: GenerationJob) => void;
  onSelect: (jobId: string) => void;
}

export function GenerationCard({ active, job, onCopyParams, onRetry, onSelect }: GenerationCardProps) {
  const dimensions = job.width && job.height ? `${job.width}x${job.height}` : "模板尺寸";

  return (
    <ElectricBorder active={active}>
      <article
        className={cn(
          "rounded-md border border-border/70 bg-background/38 p-4",
          active && "border-primary/70 bg-primary/10",
        )}
      >
        <button className="block w-full text-left" onClick={() => onSelect(job.id)} type="button">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="ops-kicker">Generation Job</p>
              <h3 className="mt-1 font-display text-base font-semibold">{job.workflow_id ?? "default workflow"}</h3>
            </div>
            <Badge variant={statusVariant(job.status)}>{statusLabel(job.status)}</Badge>
          </div>

          <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted-foreground">{job.prompt}</p>

          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
              <span>进度</span>
              <span>{job.progress}%</span>
            </div>
            <Progress value={job.progress} />
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-3 text-xs text-muted-foreground sm:grid-cols-4">
            <div>
              <dt className="text-foreground">Provider</dt>
              <dd>{job.provider}</dd>
            </div>
            <div>
              <dt className="text-foreground">时长</dt>
              <dd>{formatDuration(job.duration)}</dd>
            </div>
            <div>
              <dt className="text-foreground">尺寸</dt>
              <dd>{dimensions}</dd>
            </div>
            <div>
              <dt className="text-foreground">FPS</dt>
              <dd>{job.fps ?? "-"}</dd>
            </div>
          </dl>
        </button>

        <div className="mt-4 flex flex-wrap gap-2">
          <ClickSpark>
            <Button onClick={() => onRetry(job)} size="sm" type="button" variant="secondary">
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              复用参数
            </Button>
          </ClickSpark>
          <Button onClick={() => onCopyParams(job)} size="sm" type="button" variant="ghost">
            <Copy className="h-4 w-4" aria-hidden="true" />
            复制参数
          </Button>
          <Button onClick={() => onSelect(job.id)} size="sm" type="button" variant="ghost">
            <Workflow className="h-4 w-4" aria-hidden="true" />
            查看快照
          </Button>
        </div>
      </article>
    </ElectricBorder>
  );
}
