import * as React from "react";
import { Check, ChevronLeft, ChevronRight, FolderKanban, Plus, Search, Settings, SquareStack, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createProject, projectQueries } from "@/api/projects";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DarkVeil } from "@/components/react-bits/DarkVeil";
import StarBorder from "@/components/StarBorder";
import { GlobalTaskManager, useGlobalTasks } from "@/features/tasks/GlobalTaskManager";
import { isActiveJob } from "@/features/tasks/taskModel";
import { projectStageLabel } from "@/features/projects/projectFormat";
import { gsap, useGSAP } from "@/lib/gsap";
import { newIds } from "@/lib/motionState";
import { cn } from "@/lib/utils";

interface AppShellProps {
  activeProjectId: string | null;
  children: React.ReactNode;
  contentKey?: string;
  onNavigate: (hash: string) => void;
}

function ProjectSidebar({ activeProjectId, onNavigate }: Omit<AppShellProps, "children">) {
  const [collapsed, setCollapsed] = React.useState(() => localStorage.getItem("military.sidebar.collapsed") === "1");
  const [search, setSearch] = React.useState("");
  const [createOpen, setCreateOpen] = React.useState(false);
  const [newTitle, setNewTitle] = React.useState("");
  const [newDescription, setNewDescription] = React.useState("");
  const [createError, setCreateError] = React.useState<string | null>(null);
  const sidebarRef = React.useRef<HTMLElement>(null);
  const seenProjectIds = React.useRef(new Set<string>());
  const projectsQuery = useQuery(projectQueries.all());
  const queryClient = useQueryClient();
  const { jobsForProject } = useGlobalTasks();
  const createMutation = useMutation({
    mutationFn: () => createProject({
      title: newTitle.trim(),
      description: newDescription.trim() || null,
      status: "draft",
      current_stage: "script",
    }),
    onSuccess: async (project) => {
      setCreateOpen(false);
      setNewTitle("");
      setNewDescription("");
      setCreateError(null);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      onNavigate(`generate/project/${project.id}`);
    },
    onError: (error) => setCreateError(error instanceof Error ? error.message : "项目创建失败"),
  });
  const projects = (projectsQuery.data ?? [])
    .filter((project) => project.status !== "archived")
    .filter((project) => project.title.toLowerCase().includes(search.trim().toLowerCase()))
    .slice(0, 12);
  const projectKey = projects.map((project) => project.id).join("|");
  const progressKey = projects.map((project) => {
    const job = jobsForProject(project.id).find(isActiveJob);
    return `${project.id}:${job?.progress ?? ""}`;
  }).join("|");

  useGSAP(() => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const currentIds = projects.map((project) => project.id);
    const entering = newIds(seenProjectIds.current, currentIds);
    currentIds.forEach((id) => seenProjectIds.current.add(id));
    if (entering.length) {
      const selector = entering.map((id) => `[data-sidebar-project-id='${CSS.escape(id)}']`).join(",");
      gsap.from(selector, { autoAlpha: 0, x: reduced ? 0 : -10, duration: reduced ? 0.16 : 0.38, stagger: reduced ? 0 : 0.04, ease: "reveal", overwrite: "auto" });
    }

    sidebarRef.current?.querySelectorAll<HTMLElement>("[data-progress]").forEach((bar) => {
      gsap.to(bar, { scaleX: Number(bar.dataset.progress ?? 0) / 100, duration: 0.55, ease: "interface", overwrite: "auto" });
    });
  }, { scope: sidebarRef, dependencies: [activeProjectId, projectKey, progressKey, collapsed], revertOnUpdate: true });

  function toggle() {
    setCollapsed((value) => {
      localStorage.setItem("military.sidebar.collapsed", value ? "0" : "1");
      return !value;
    });
  }

  function openCreate() {
    if (collapsed) {
      localStorage.setItem("military.sidebar.collapsed", "0");
      setCollapsed(false);
    }
    setCreateOpen(true);
    setCreateError(null);
  }

  function submitCreate(event: React.FormEvent) {
    event.preventDefault();
    if (newTitle.trim()) createMutation.mutate();
  }

  return <aside className={cn("project-sidebar", collapsed && "project-sidebar--collapsed")} ref={sidebarRef}>
    <div className="project-sidebar__brand"><span className="project-sidebar__mark">MV</span>{collapsed ? null : <div><strong>军事视频工作台</strong><span>MILITARY VIDEO STUDIO</span></div>}</div>
    <Button aria-label="新建项目" className="w-full justify-start" onClick={openCreate} size="sm" type="button"><Plus className="h-4 w-4" />{collapsed ? null : "新建项目"}</Button>
    {!collapsed && createOpen ? <form className="project-sidebar__create" onSubmit={submitCreate}>
      <div className="project-sidebar__create-heading"><span>建立项目档案</span><button aria-label="关闭新建项目界面" onClick={() => setCreateOpen(false)} type="button"><X className="h-3.5 w-3.5" /></button></div>
      <label><span>项目名称</span><Input autoFocus maxLength={255} onChange={(event) => setNewTitle(event.target.value)} placeholder="例如：远程预警体系" value={newTitle} /></label>
      <label><span>任务说明</span><textarea onChange={(event) => setNewDescription(event.target.value)} placeholder="选题、受众或交付目标" rows={3} value={newDescription} /></label>
      {createError ? <p role="alert">{createError}</p> : null}
      <Button className="w-full" disabled={!newTitle.trim()} isLoading={createMutation.isPending} size="sm" type="submit"><Check className="h-4 w-4" />创建并进入</Button>
    </form> : null}
    {collapsed ? null : <label className="project-sidebar__search"><Search className="h-4 w-4" /><Input aria-label="搜索项目" onChange={(event) => setSearch(event.target.value)} placeholder="搜索项目" value={search} /></label>}
    <nav className="project-sidebar__nav" aria-label="项目导航">
      <button className="project-sidebar__all" onClick={() => onNavigate("projects")} type="button"><SquareStack className="h-4 w-4" />{collapsed ? null : "所有项目"}</button>
      {projects.map((project) => {
        const activeJob = jobsForProject(project.id).find(isActiveJob);
        const isActive = activeProjectId === project.id;
        return <StarBorder className={cn("project-sidebar__project", isActive && "is-active")} color={isActive ? "#8fa45f" : "transparent"} data-active={isActive ? "true" : "false"} data-sidebar-project-id={project.id} key={project.id} onClick={() => onNavigate(`generate/project/${project.id}`)} speed={isActive ? "4s" : "0s"} thickness={2} type="button">
          <FolderKanban className="h-4 w-4 shrink-0" />
          {collapsed ? (activeJob ? <span className="project-sidebar__pulse" /> : null) : <><span className="min-w-0 flex-1"><strong>{project.title}</strong><small>{projectStageLabel(project.current_stage)}</small></span>{activeJob ? <span className="project-sidebar__job"><i data-progress={activeJob.progress} />{Math.round(activeJob.progress)}%</span> : null}</>}
        </StarBorder>;
      })}
    </nav>
    <div className="project-sidebar__footer">
      <button onClick={() => onNavigate("settings")} type="button"><Settings className="h-4 w-4" />{collapsed ? null : "设置"}</button>
      <button aria-label={collapsed ? "展开侧边栏" : "折叠侧边栏"} onClick={toggle} type="button">{collapsed ? <ChevronRight className="h-4 w-4" /> : <><ChevronLeft className="h-4 w-4" />折叠</>}</button>
    </div>
  </aside>;
}

export function AppShell(props: AppShellProps) {
  const contentRef = React.useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    gsap.fromTo(contentRef.current, { autoAlpha: 0, y: reduced ? 0 : 14 }, { autoAlpha: 1, y: 0, duration: reduced ? 0.18 : 0.48, ease: "reveal", overwrite: "auto", clearProps: "transform,opacity,visibility" });
  }, { scope: contentRef, dependencies: [props.contentKey], revertOnUpdate: true });
  return <GlobalTaskManager><div className="app-shell"><DarkVeil /><ProjectSidebar activeProjectId={props.activeProjectId} onNavigate={props.onNavigate} /><div className="app-shell__content" ref={contentRef}>{props.children}</div></div></GlobalTaskManager>;
}
