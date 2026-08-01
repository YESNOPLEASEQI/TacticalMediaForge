import { Badge } from "@/components/ui/badge";
import { SectionPanel } from "@/components/operations/OperationsShell";
import { formatProjectDate, jobStatusLabel } from "@/features/projects/projectFormat";
import { restoreProjectWorkflow } from "@/features/projects/projectModel";
import type { ProjectWorkspace } from "@/types/projects";
import { useGlobalTasksOptional } from "@/features/tasks/GlobalTaskManager";
import { applyProjectJobsToDraft } from "@/features/tasks/taskModel";

export type ProjectDetailTab = "overview" | "script" | "storyboard" | "assets" | "jobs" | "outputs";

interface ProjectDetailSectionProps {
  tab: Exclude<ProjectDetailTab, "overview">;
  workspace: ProjectWorkspace;
}

export function ProjectDetailSection({ tab, workspace }: ProjectDetailSectionProps) {
  const globalTasks = useGlobalTasksOptional();
  const draft = applyProjectJobsToDraft(restoreProjectWorkflow(workspace, null), globalTasks?.jobsForProject(workspace.project.id) ?? []);
  const history = workspace.history;

  if (tab === "script") {
    return <SectionPanel title="脚本">
      <div className="script-editor">{draft.narrations.filter((item) => item.trim()).map((item, index) => <article className="script-paragraph" key={`${index}-${item.slice(0, 12)}`}><span className="script-paragraph__index">{String(index + 1).padStart(2, "0")}</span><p className="py-2 text-sm leading-7">{item}</p><span className="pt-3 text-right font-data text-xs text-muted-foreground">{item.replace(/\s/g, "").length}</span></article>)}</div>
      {!draft.narrations.some((item) => item.trim()) ? <p className="text-sm text-muted-foreground">尚无脚本内容。</p> : null}
    </SectionPanel>;
  }

  if (tab === "storyboard") {
    return <SectionPanel title={`分镜 · ${draft.storyboard.length} 镜`}>
      <div className="grid gap-3 lg:grid-cols-2">{draft.storyboard.map((scene) => <article className="storyboard-card" key={scene.id}><div className="storyboard-card__header"><span className="font-data text-xs text-primary">SCENE {String(scene.index + 1).padStart(2, "0")}</span><Badge variant={scene.status === "completed" ? "success" : "secondary"}>{scene.assetType}</Badge></div><div className="space-y-3 p-4"><p className="text-sm leading-6">{scene.narration}</p><div><p className="text-xs text-muted-foreground">英文生成提示词</p><p className="mt-1 line-clamp-5 font-data text-xs leading-5 text-muted-foreground">{scene.mediaPrompt || "未填写"}</p></div></div></article>)}</div>
      {!draft.storyboard.length ? <p className="text-sm text-muted-foreground">尚无分镜记录。</p> : null}
    </SectionPanel>;
  }

  if (tab === "assets") {
    return <SectionPanel title={`资产 · ${history?.assets.length ?? 0}`}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{history?.assets.map((asset) => <article className="ops-panel-muted overflow-hidden" key={asset.id}>{asset.asset_type === "image" && asset.url ? <img alt={asset.filename ?? "项目图片资产"} className="aspect-video w-full object-cover" src={asset.url} /> : asset.asset_type === "video" && asset.url ? <video className="aspect-video w-full bg-black object-cover" muted preload="metadata" src={asset.url} /> : <div className="flex aspect-video items-center justify-center font-data text-xs text-muted-foreground">{asset.asset_type.toUpperCase()}</div>}<div className="p-3"><p className="truncate text-sm font-medium">{asset.filename ?? asset.id}</p><p className="mt-1 font-data text-xs text-muted-foreground">{asset.asset_type} · {asset.duration ? `${asset.duration.toFixed(1)}s` : "无时长"}</p></div></article>)}</div>
      {!history?.assets.length ? <p className="text-sm text-muted-foreground">尚无正式资产。</p> : null}
    </SectionPanel>;
  }

  if (tab === "jobs") {
    return <SectionPanel title={`生成记录 · ${history?.generation_jobs.length ?? 0}`}>
      <div className="space-y-3">{history?.generation_jobs.map((job) => <article className="ops-panel-muted grid gap-3 p-4 md:grid-cols-[1fr_180px_140px]" key={job.id}><div><p className="text-sm font-medium">视频生成</p><details className="mt-2 text-xs"><summary className="cursor-pointer text-muted-foreground">技术详情</summary><dl className="mt-2 space-y-2"><div><dt className="text-muted-foreground">任务编号</dt><dd className="break-all font-data">{job.id}</dd></div><div><dt className="text-muted-foreground">生成方式</dt><dd>{job.provider} · {job.workflow_id ?? "未记录"}{job.model_name ? ` · ${job.model_name}` : ""}</dd></div></dl></details></div><div><p className="text-xs text-muted-foreground">提交时间</p><p className="mt-1 text-sm">{formatProjectDate(job.created_at)}</p></div><div className="flex items-center justify-between md:block"><Badge variant={job.status === "success" ? "success" : job.status === "failed" ? "destructive" : "warning"}>{jobStatusLabel(job.status)}</Badge><p className="mt-2 font-data text-xs">{job.progress}%</p></div></article>)}</div>
      {!history?.generation_jobs.length ? <p className="text-sm text-muted-foreground">尚未提交生成任务。</p> : null}
    </SectionPanel>;
  }

  const videos = history?.assets.filter((asset) => asset.asset_type === "video" && asset.url) ?? [];
  const latest = history?.session.video_url ?? videos[0]?.url;
  return <SectionPanel title="成片">
    {latest ? <video className="aspect-video w-full max-w-5xl rounded-sm border border-border bg-black" controls preload="metadata" src={latest} /> : <p className="text-sm text-muted-foreground">尚无正式成片。</p>}
    {videos.length > 1 ? <div className="mt-4 grid gap-3 md:grid-cols-3">{videos.slice(1).map((asset) => <video className="aspect-video w-full rounded-sm border border-border bg-black object-cover" key={asset.id} muted preload="metadata" src={asset.url ?? undefined} />)}</div> : null}
  </SectionPanel>;
}
