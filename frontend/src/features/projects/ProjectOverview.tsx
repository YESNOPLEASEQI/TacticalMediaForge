import { Activity, FileText, Film, PanelsTopLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { ProjectStageRail } from "@/features/projects/ProjectStageRail";
import { formatProjectDate, jobStatusLabel, projectStageLabel } from "@/features/projects/projectFormat";
import { restoreProjectWorkflow } from "@/features/projects/projectModel";
import type { ProjectWorkspace } from "@/types/projects";
import { useGlobalTasksOptional } from "@/features/tasks/GlobalTaskManager";
import { applyProjectJobsToDraft } from "@/features/tasks/taskModel";

interface ProjectOverviewProps {
  workspace: ProjectWorkspace;
}

export function ProjectOverview({ workspace }: ProjectOverviewProps) {
  const { project, history } = workspace;
  const globalTasks = useGlobalTasksOptional();
  const draft = applyProjectJobsToDraft(restoreProjectWorkflow(workspace, null), globalTasks?.jobsForProject(project.id) ?? []);
  const latestJob = history?.generation_jobs[0] ?? null;
  const latestVideo = history?.session.video_url ??
    history?.assets.find((asset) => asset.asset_type === "video" && asset.metadata.role === "final_video")?.url ??
    null;
  const hasScript = draft.narrations.some((item) => item.trim()) || Boolean(project.source_text);
  const hasStoryboard = draft.storyboard.length > 0;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.8fr)]">
      <div className="space-y-4">
        <SectionPanel title="项目概况">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div><dt className="text-xs text-muted-foreground">项目编号</dt><dd className="mt-1 font-data text-sm">{project.id.slice(0, 13)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">当前阶段</dt><dd className="mt-1 text-sm">{projectStageLabel(project.current_stage)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">创建时间</dt><dd className="mt-1 text-sm">{formatProjectDate(project.created_at)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">最后更新</dt><dd className="mt-1 text-sm">{formatProjectDate(project.updated_at)}</dd></div>
          </dl>
          {project.description ? <p className="mt-4 border-l-2 border-primary/60 pl-3 text-sm leading-6 text-muted-foreground">{project.description}</p> : null}
        </SectionPanel>

        <SectionPanel title="阶段进度">
          <ProjectStageRail currentStage={project.current_stage} hasScript={hasScript} hasStoryboard={hasStoryboard} hasVideo={Boolean(latestVideo)} />
        </SectionPanel>

        <div className="grid gap-4 md:grid-cols-2">
          <SectionPanel title="最新脚本">
            <div className="mb-3 flex items-center justify-between"><FileText className="h-5 w-5 text-primary" /><Badge variant={draft.scriptConfirmed ? "success" : "secondary"}>{draft.scriptConfirmed ? "已确认" : "编辑中"}</Badge></div>
            <p className="line-clamp-6 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{draft.narrations.filter(Boolean).join("\n\n") || project.source_text || "尚未建立脚本内容。"}</p>
          </SectionPanel>
          <SectionPanel title="最新分镜">
            <div className="mb-3 flex items-center justify-between"><PanelsTopLeft className="h-5 w-5 text-primary" /><span className="font-data text-sm">{draft.storyboard.length} 镜</span></div>
            <div className="space-y-2">
              {draft.storyboard.slice(0, 3).map((scene) => <p className="line-clamp-2 rounded-sm border border-border/60 bg-background/35 p-2 text-xs text-muted-foreground" key={scene.id}><span className="mr-2 font-data text-primary">{String(scene.index + 1).padStart(2, "0")}</span>{scene.narration}</p>)}
              {!draft.storyboard.length ? <p className="text-sm text-muted-foreground">脚本确认后可生成分镜。</p> : null}
            </div>
          </SectionPanel>
        </div>
      </div>

      <div className="space-y-4">
        <SectionPanel title="最近任务">
          <div className="flex items-center justify-between"><Activity className="h-5 w-5 text-primary" /><Badge variant={latestJob?.status === "success" ? "success" : latestJob?.status === "failed" ? "destructive" : "secondary"}>{jobStatusLabel(latestJob?.status)}</Badge></div>
          {latestJob ? <div className="mt-4 space-y-3 text-sm"><div><p className="text-xs text-muted-foreground">进度</p><p className="mt-1">{latestJob.progress}%</p></div><details className="rounded-md border border-border/60 p-3 text-xs"><summary className="cursor-pointer text-muted-foreground">技术详情</summary><dl className="mt-3 space-y-2"><div><dt className="text-muted-foreground">任务编号</dt><dd className="mt-1 break-all font-data">{latestJob.id}</dd></div><div><dt className="text-muted-foreground">生成方式</dt><dd className="mt-1">{latestJob.provider} · {latestJob.workflow_id ?? "未记录"}</dd></div></dl></details></div> : <p className="mt-4 text-sm text-muted-foreground">尚未提交视频生成任务。</p>}
        </SectionPanel>

        <SectionPanel title="最新成片">
          {latestVideo ? <video className="aspect-video w-full rounded-sm border border-border bg-black object-cover" controls preload="metadata" src={latestVideo} /> : <div className="flex aspect-video items-center justify-center rounded-sm border border-dashed border-border bg-background/35 text-sm text-muted-foreground"><Film className="mr-2 h-5 w-5" />等待视频生成完成</div>}
        </SectionPanel>
      </div>
    </div>
  );
}
