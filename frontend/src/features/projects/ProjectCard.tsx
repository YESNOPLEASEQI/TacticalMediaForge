import * as React from "react";
import { Archive, ArrowUpRight, Clock3, Film, FolderOpen, MoreHorizontal, Pencil, Play, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ProjectCardData } from "@/types/projects";
import { ProjectStageRail } from "@/features/projects/ProjectStageRail";
import { formatProjectDate, jobStatusLabel, projectStatusLabel, projectStatusVariant } from "@/features/projects/projectFormat";
import { gsap, useGSAP } from "@/lib/gsap";

interface ProjectCardProps {
  project: ProjectCardData;
  selected?: boolean;
  onSelectedChange?: (projectId: string, selected: boolean) => void;
  onArchive: (project: ProjectCardData) => void;
  onContinue: (projectId: string) => void;
  onDelete: (project: ProjectCardData) => void;
  onOpen: (projectId: string) => void;
  onRename: (projectId: string, title: string) => void;
}

export function ProjectCard({ project, selected = false, onSelectedChange, onArchive, onContinue, onDelete, onOpen, onRename }: ProjectCardProps) {
  const [renaming, setRenaming] = React.useState(false);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [title, setTitle] = React.useState(project.title);
  const cardRef = React.useRef<HTMLElement>(null);
  const menuRef = React.useRef<HTMLDivElement>(null);
  const isArchived = project.status === "archived";
  const videoJobActive = project.latestJobType === "video_generation" && (project.latestJobStatus === "queued" || project.latestJobStatus === "running");
  const actionLabel = videoJobActive
    ? "查看生成进度"
    : project.videoUrl && project.hasUnsubmittedChanges
      ? "继续修改"
      : project.videoUrl
        ? "查看成片"
        : project.current_stage === "storyboard"
          ? "继续分镜"
          : project.current_stage === "video"
            ? "进入生成"
            : "继续脚本";
  const progressLabel = videoJobActive && project.latestJobCurrentScene && project.latestJobTotalScenes
    ? `SHOT ${String(project.latestJobCurrentScene).padStart(2, "0")} / ${String(project.latestJobTotalScenes).padStart(2, "0")}`
    : videoJobActive && project.latestJobProgress != null
      ? `${Math.round(project.latestJobProgress)}%`
      : jobStatusLabel(project.latestJobStatus);

  const { contextSafe } = useGSAP({ scope: cardRef });

  const animateHover = contextSafe((active: boolean) => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    gsap.to(cardRef.current, {
      y: active ? -6 : 0,
      scale: active ? 1.008 : 1,
      duration: active ? 0.42 : 0.32,
      ease: "interface",
      overwrite: "auto",
    });
    gsap.to("[data-motion='project-media']", {
      scale: active ? 1.035 : 1,
      duration: active ? 0.65 : 0.4,
      ease: "reveal",
      overwrite: "auto",
    });
  });

  React.useEffect(() => {
    if (!menuOpen) return;
    const close = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  function submitRename(event: React.FormEvent) {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle || nextTitle === project.title) {
      setTitle(project.title);
      setRenaming(false);
      return;
    }
    onRename(project.id, nextTitle);
    setRenaming(false);
  }

  return (
    <article
      className={`project-card${selected ? " project-card--selected" : ""}`}
      data-motion="project-card"
      data-project-id={project.id}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) animateHover(false); }}
      onFocus={() => animateHover(true)}
      onMouseEnter={() => animateHover(true)}
      onMouseLeave={() => animateHover(false)}
      ref={cardRef}
    >
      <label className="project-card__selector">
        <input
          aria-label={`选择项目 ${project.title}`}
          checked={selected}
          onChange={(event) => onSelectedChange?.(project.id, event.target.checked)}
          type="checkbox"
        />
        <span aria-hidden="true" />
      </label>
      <div className="project-card__preview" data-motion="project-media">
        {project.thumbnailUrl ? <img alt={`${project.title} 缩略图`} className="h-full w-full object-cover" src={project.thumbnailUrl} /> : project.videoUrl ? <video aria-label={`${project.title} 最新视频`} className="h-full w-full object-cover" muted preload="metadata" src={project.videoUrl} /> : <div className="project-card__empty-preview"><FolderOpen className="h-8 w-8" aria-hidden="true" /><span>等待首个成片</span></div>}
        <span className="project-card__scan" aria-hidden="true" />
        <span className="project-card__index">PRJ / {project.id.slice(0, 8).toUpperCase()}</span>
      </div>

      <div className="space-y-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            {renaming ? (
              <form className="flex gap-2" onSubmit={submitRename}>
                <label className="sr-only" htmlFor={`rename-${project.id}`}>项目名称</label>
                <Input autoFocus id={`rename-${project.id}`} onChange={(event) => setTitle(event.target.value)} value={title} />
                <Button size="sm" type="submit">保存</Button>
              </form>
            ) : (
              <button className="group text-left" onClick={() => onOpen(project.id)} type="button">
                <h2 className="line-clamp-2 font-display text-lg font-semibold group-hover:text-primary">{project.title}</h2>
                <span className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">查看项目档案 <ArrowUpRight className="h-3 w-3" aria-hidden="true" /></span>
              </button>
            )}
          </div>
          <Badge variant={projectStatusVariant(project.status)}>{projectStatusLabel(project.status)}</Badge>
        </div>

        <ProjectStageRail compact currentStage={project.current_stage} hasScript={Boolean(project.source_text || project.settings_json.workspace_draft)} hasStoryboard={project.storyboardCount > 0} hasVideo={Boolean(project.videoUrl)} />

        <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
          <div><dt className="text-muted-foreground">分镜数量</dt><dd className="mt-0.5">{project.storyboardCount} 镜</dd></div>
          <div><dt className="text-muted-foreground">当前状态</dt><dd className="mt-0.5">{progressLabel}</dd></div>
          <div className="col-span-2"><dt className="text-muted-foreground">更新时间</dt><dd className="mt-0.5 flex items-center gap-1"><Clock3 className="h-3 w-3" />{formatProjectDate(project.updated_at)}</dd></div>
        </dl>

        <div className="flex items-center gap-2 border-t border-border/70 pt-3">
          <Button disabled={isArchived} onClick={() => onContinue(project.id)} size="sm" type="button"><Play className="h-3.5 w-3.5" aria-hidden="true" />{actionLabel}</Button>
          {project.videoUrl ? <Film className="h-4 w-4 text-accent" aria-label="已有成片" /> : null}
          <div className="relative ml-auto" ref={menuRef}>
            <Button aria-expanded={menuOpen} aria-label="更多项目操作" onClick={() => setMenuOpen((value) => !value)} size="icon" type="button" variant="ghost"><MoreHorizontal className="h-4 w-4" /></Button>
            {menuOpen ? (
              <div className="absolute bottom-full right-0 z-30 mb-1 w-32 rounded-md border border-border bg-popover p-1 shadow-lg">
                <button className="flex w-full items-center gap-2 rounded-sm px-2.5 py-2 text-left text-xs hover:bg-muted" onClick={() => { setMenuOpen(false); setRenaming(true); }} type="button"><Pencil className="h-3.5 w-3.5" />重命名</button>
                <button className="flex w-full items-center gap-2 rounded-sm px-2.5 py-2 text-left text-xs hover:bg-muted disabled:opacity-50" disabled={isArchived} onClick={() => { setMenuOpen(false); onArchive(project); }} type="button"><Archive className="h-3.5 w-3.5" />归档</button>
                <button className="flex w-full items-center gap-2 rounded-sm px-2.5 py-2 text-left text-xs text-destructive hover:bg-muted" onClick={() => { setMenuOpen(false); onDelete(project); }} type="button"><Trash2 className="h-3.5 w-3.5" />删除</button>
              </div>
            ) : null}
          </div>
        </div>
        {isArchived ? <p className="text-xs text-muted-foreground">项目已归档，恢复后才能继续编辑。</p> : null}
      </div>
    </article>
  );
}
