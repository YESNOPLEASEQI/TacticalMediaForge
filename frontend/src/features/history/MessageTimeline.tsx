import { Bot, UserRound } from "lucide-react";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { AnimatedList } from "@/components/react-bits/AnimatedList";
import type { GenerationJob, HistoryMessage } from "@/types/history";
import { GenerationCard } from "@/features/history/GenerationCard";
import { formatDateTime } from "@/features/history/historyFormat";

interface MessageTimelineProps {
  activeJobId: string | null;
  jobs: GenerationJob[];
  messages: HistoryMessage[];
  onCopyParams: (job: GenerationJob) => void;
  onRetry: (job: GenerationJob) => void;
  onSelectJob: (jobId: string) => void;
}

export function MessageTimeline({
  activeJobId,
  jobs,
  messages,
  onCopyParams,
  onRetry,
  onSelectJob,
}: MessageTimelineProps) {
  const assistantMessage = messages.find((message) => message.role === "assistant");
  const scenes = assistantMessage?.content.scenes ?? [];
  const sceneItems = scenes.map((scene) => `${scene.index + 1}. ${scene.narration}`);

  return (
    <SectionPanel className="min-h-[calc(100vh-13rem)]" description="记录输入、Agent 拆解和生成任务，供复现与排错。" eyebrow="Timeline" title="生成时间线">
      <div className="space-y-4">
        {messages.length === 0 ? (
          <p className="ops-panel-muted p-3 text-sm text-muted-foreground">选择一个 Session 后查看生成过程。</p>
        ) : null}

        {messages.map((message) => (
          <article className="ops-panel-muted p-4" key={message.id}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary">
                  {message.role === "user" ? (
                    <UserRound className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Bot className="h-4 w-4" aria-hidden="true" />
                  )}
                </span>
                <div>
                  <p className="text-sm font-semibold">{message.role === "user" ? "用户输入" : "Agent 拆解"}</p>
                  <p className="text-xs text-muted-foreground">{formatDateTime(message.created_at)}</p>
                </div>
              </div>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
              {message.content.text || "无文本内容"}
            </p>
          </article>
        ))}

        {sceneItems.length > 0 ? (
          <section className="ops-panel-muted p-4">
            <div className="mb-3">
              <p className="text-sm font-semibold">分镜快照</p>
              <p className="text-xs text-muted-foreground">来自 storyboard，可用于复现或继续编辑。</p>
            </div>
            <AnimatedList activeIndex={sceneItems.length - 1} items={sceneItems} />
          </section>
        ) : null}

        {jobs.map((job) => (
          <GenerationCard
            active={job.id === activeJobId}
            job={job}
            key={job.id}
            onCopyParams={onCopyParams}
            onRetry={onRetry}
            onSelect={onSelectJob}
          />
        ))}
      </div>
    </SectionPanel>
  );
}
