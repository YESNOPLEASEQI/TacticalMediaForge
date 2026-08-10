import * as React from "react";
import { Archive, CheckSquare2, FolderKanban, Plus, RotateCcw, Search, SlidersHorizontal, Trash2, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createProject, deleteProject, projectQueries, updateProject } from "@/api/projects";
import { OperationsShell, StatusStrip, WorkbenchHeader } from "@/components/operations/OperationsShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ProjectCard } from "@/features/projects/ProjectCard";
import { useGlobalTasksOptional } from "@/features/tasks/GlobalTaskManager";
import { Flip, gsap, useGSAP } from "@/lib/gsap";
import { newIds } from "@/lib/motionState";
import type { ProjectCardData, ProjectCreate, ProjectUpdate } from "@/types/projects";

interface ProjectCenterPageProps {
  onContinue: (projectId: string) => void;
  onOpenProject: (projectId: string) => void;
}

function matches(project: ProjectCardData, search: string, status: string) {
  const statusMatches = status === "all"
    ? project.status !== "archived"
    : project.status === status;
  if (!statusMatches) return false;
  const needle = search.trim().toLowerCase();
  if (!needle) return true;
  return [project.title, project.description, project.id, project.current_stage, project.status]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(needle));
}

export function ProjectCenterPage({
  onContinue,
  onOpenProject,
}: ProjectCenterPageProps) {
  const [search, setSearch] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [showCreate, setShowCreate] = React.useState(false);
  const [newTitle, setNewTitle] = React.useState("");
  const [newDescription, setNewDescription] = React.useState("");
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(() => new Set());
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const pageRef = React.useRef<HTMLDivElement>(null);
  const gridRef = React.useRef<HTMLDivElement>(null);
  const seenProjectIds = React.useRef(new Set<string>());
  const introPlayed = React.useRef(false);
  const queryClient = useQueryClient();
  const globalTasks = useGlobalTasksOptional();
  const jobsForProject = globalTasks?.jobsForProject ?? (() => []);
  const projectsQuery = useQuery(projectQueries.all());

  const refresh = React.useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
    [queryClient],
  );

  const createMutation = useMutation({
    mutationFn: (payload: ProjectCreate) => createProject(payload),
    onSuccess: async (project) => {
      setShowCreate(false);
      setNewTitle("");
      setNewDescription("");
      setErrorMessage(null);
      await refresh();
      onContinue(project.id);
    },
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "项目创建失败"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProjectUpdate }) => updateProject(id, payload),
    onSuccess: async () => {
      setErrorMessage(null);
      await refresh();
    },
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "项目更新失败"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: async () => {
      setErrorMessage(null);
      await refresh();
    },
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "项目删除失败"),
  });

  const bulkMutation = useMutation({
    mutationFn: async (action: "archive" | "restore" | "delete") => {
      const ids = [...selectedIds];
      if (action === "delete") {
        await Promise.all(ids.map((id) => deleteProject(id)));
      } else {
        const archived = action === "archive";
        await Promise.all(ids.map((id) => updateProject(id, {
          status: archived ? "archived" : "active",
          archived_at: archived ? new Date().toISOString() : null,
        })));
      }
      return ids;
    },
    onSuccess: async () => {
      setSelectedIds(new Set());
      setErrorMessage(null);
      await refresh();
    },
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "批量处理失败"),
  });

  const projects = projectsQuery.data ?? [];
  const visibleProjects = React.useMemo(
    () => projects.filter((project) => matches(project, search, statusFilter)),
    [projects, search, statusFilter],
  );
  const activeCount = projects.filter((project) => project.status === "active" || project.status === "draft").length;
  const completedCount = projects.filter((project) => project.status === "completed").length;
  const archivedCount = projects.filter((project) => project.status === "archived").length;
  const visibleProjectKey = visibleProjects.map((project) => project.id).join("|");
  const visibleIds = visibleProjects.map((project) => project.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));
  const selectedProjects = projects.filter((project) => selectedIds.has(project.id));
  const canArchiveSelected = selectedProjects.some((project) => project.status !== "archived");
  const canRestoreSelected = selectedProjects.some((project) => project.status === "archived");

  React.useEffect(() => {
    const available = new Set(projects.map((project) => project.id));
    setSelectedIds((current) => {
      const next = new Set([...current].filter((id) => available.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [projects]);

  React.useEffect(() => {
    setSelectedIds(new Set());
  }, [search, statusFilter]);

  const { contextSafe } = useGSAP({ scope: pageRef });

  useGSAP(() => {
    if (projectsQuery.isPending) return;
    const currentIds = visibleProjects.map((project) => project.id);
    const enteringIds = newIds(seenProjectIds.current, currentIds);
    currentIds.forEach((id) => seenProjectIds.current.add(id));
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

    if (!introPlayed.current) {
      introPlayed.current = true;
      const timeline = gsap.timeline({ defaults: { ease: "reveal", overwrite: "auto" } });
      timeline
        .from("[data-motion='project-heading']", { autoAlpha: 0, y: reduced ? 0 : 18, duration: reduced ? 0.18 : 0.55 })
        .from("[data-motion='project-stat']", { autoAlpha: 0, y: reduced ? 0 : 12, duration: reduced ? 0.16 : 0.42, stagger: reduced ? 0 : 0.055 }, "-=0.28")
        .from("[data-motion='project-controls']", { autoAlpha: 0, y: reduced ? 0 : 10, duration: reduced ? 0.16 : 0.42 }, "-=0.24")
        .from("[data-motion='project-card']", { autoAlpha: 0, y: reduced ? 0 : 24, scale: reduced ? 1 : 0.975, duration: reduced ? 0.18 : 0.62, stagger: reduced ? 0 : 0.085 }, "-=0.2");
      if (!reduced) timeline.fromTo(".project-card__scan", { xPercent: -140 }, { xPercent: 150, duration: 0.72, stagger: 0.085, ease: "power2.inOut" }, "-=0.58");
      return;
    }

    if (!enteringIds.length) return;
    const selector = enteringIds.map((id) => `[data-project-id='${CSS.escape(id)}']`).join(",");
    gsap.fromTo(selector, { autoAlpha: 0, y: reduced ? 0 : 18, scale: reduced ? 1 : 0.98 }, { autoAlpha: 1, y: 0, scale: 1, duration: reduced ? 0.18 : 0.48, stagger: reduced ? 0 : 0.065, ease: "reveal", overwrite: "auto" });
  }, { scope: pageRef, dependencies: [projectsQuery.isPending, visibleProjectKey], revertOnUpdate: true });

  useGSAP(() => {
    if (!showCreate) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    gsap.from("[data-motion='create-project']", { autoAlpha: 0, y: reduced ? 0 : -12, clipPath: reduced ? "inset(0 0 0 0)" : "inset(0 0 100% 0)", duration: reduced ? 0.18 : 0.45, ease: "reveal", overwrite: "auto" });
  }, { scope: pageRef, dependencies: [showCreate], revertOnUpdate: true });

  const updateLayout = contextSafe((update: () => void) => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      update();
      return;
    }
    const cards = gridRef.current?.querySelectorAll("[data-motion='project-card']");
    const state = cards?.length ? Flip.getState(cards) : null;
    update();
    if (!state) return;
    requestAnimationFrame(contextSafe(() => {
      Flip.from(state, { duration: 0.45, ease: "interface", absolute: true, stagger: 0.025, prune: true });
    }));
  });

  const animateMutation = contextSafe((projectId: string, action: () => void, remove: boolean) => {
    const target = pageRef.current?.querySelector<HTMLElement>(`[data-project-id='${CSS.escape(projectId)}']`);
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    if (!target || reduced) { action(); return; }
    gsap.to(target, {
      autoAlpha: remove ? 0 : 0.45,
      x: remove ? 24 : 8,
      scale: 0.985,
      duration: 0.28,
      ease: "interface",
      overwrite: "auto",
      onComplete: () => {
        action();
        if (!remove) gsap.to(target, { autoAlpha: 1, x: 0, scale: 1, duration: 0.36, ease: "reveal", overwrite: "auto" });
      },
    });
  });

  function submitProject(event: React.FormEvent) {
    event.preventDefault();
    if (!newTitle.trim()) return;
    createMutation.mutate({
      title: newTitle.trim(),
      description: newDescription.trim() || null,
      status: "draft",
      current_stage: "script",
      project_type: "video_agent",
      settings_json: {},
    });
  }

  function toggleProject(projectId: string, selected: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (selected) next.add(projectId);
      else next.delete(projectId);
      return next;
    });
  }

  function toggleVisibleProjects() {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) visibleIds.forEach((id) => next.delete(id));
      else visibleIds.forEach((id) => next.add(id));
      return next;
    });
  }

  function runBulk(action: "archive" | "restore" | "delete") {
    if (action === "delete" && !window.confirm(`软删除已选择的 ${selectedIds.size} 个项目？媒体文件仍会保留。`)) return;
    bulkMutation.mutate(action);
  }

  return (
    <OperationsShell>
      <div ref={pageRef}>
      <div data-motion="project-heading"><WorkbenchHeader
        actions={
          <>
            <Button onClick={() => setShowCreate((value) => !value)} size="sm" type="button">
              <Plus className="h-4 w-4" aria-hidden="true" />新建项目
            </Button>
          </>
        }
        title="项目中心"
      /></div>

      <div className="mb-4" data-motion="project-stat">
        <StatusStrip items={[
          { label: "项目总数", value: projects.length },
          { label: "创作中", value: activeCount, tone: activeCount ? "warn" : "default" },
          { label: "已完成", value: completedCount, tone: "good" },
          { label: "已归档", value: archivedCount },
        ]} />
      </div>

      {showCreate ? (
        <form
          className="ops-panel mb-4 grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)_auto]"
          data-motion="create-project"
          onSubmit={submitProject}
        >
          <div>
            <label className="control-label" htmlFor="new-project-title">项目名称</label>
            <Input id="new-project-title" maxLength={255} onChange={(event) => setNewTitle(event.target.value)} placeholder="例如：远程预警体系解析" value={newTitle} />
          </div>
          <div>
            <label className="control-label" htmlFor="new-project-description">任务说明</label>
            <Input id="new-project-description" onChange={(event) => setNewDescription(event.target.value)} placeholder="简要说明选题、受众或交付目标" value={newDescription} />
          </div>
          <Button className="self-end" disabled={!newTitle.trim()} isLoading={createMutation.isPending} type="submit">建立档案</Button>
        </form>
      ) : null}

      <div className="ops-panel mb-4 grid gap-3 p-3 md:grid-cols-[minmax(0,1fr)_220px]" data-motion="project-controls">
        <label className="relative block">
          <span className="sr-only">搜索项目</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input className="pl-9" onChange={(event) => updateLayout(() => setSearch(event.target.value))} placeholder="搜索项目名称、编号或阶段" type="search" value={search} />
        </label>
        <Select onValueChange={(value) => updateLayout(() => setStatusFilter(value))} value={statusFilter}>
          <SelectTrigger aria-label="状态筛选"><SlidersHorizontal className="h-4 w-4" /><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            <SelectItem value="draft">草稿</SelectItem>
            <SelectItem value="active">创作中</SelectItem>
            <SelectItem value="completed">已完成</SelectItem>
            <SelectItem value="archived">已归档</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {visibleProjects.length ? (
        <div className="project-batch-bar" data-active={selectedIds.size > 0 ? "true" : "false"}>
          <label className="project-batch-bar__select-all">
            <input checked={allVisibleSelected} onChange={toggleVisibleProjects} type="checkbox" />
            <span>{allVisibleSelected ? "取消全选" : "选择当前列表"}</span>
          </label>
          {selectedIds.size > 0 ? <>
            <span className="project-batch-bar__count"><CheckSquare2 className="h-4 w-4" />已选择 {selectedIds.size} 个项目</span>
            <div className="project-batch-bar__actions">
              {canArchiveSelected ? <Button disabled={bulkMutation.isPending} onClick={() => runBulk("archive")} size="sm" type="button" variant="secondary"><Archive className="h-4 w-4" />批量归档</Button> : null}
              {canRestoreSelected ? <Button disabled={bulkMutation.isPending} onClick={() => runBulk("restore")} size="sm" type="button" variant="secondary"><RotateCcw className="h-4 w-4" />恢复到所有项目</Button> : null}
              <Button disabled={bulkMutation.isPending} onClick={() => runBulk("delete")} size="sm" type="button" variant="destructive"><Trash2 className="h-4 w-4" />批量删除</Button>
              <Button aria-label="清除项目选择" onClick={() => setSelectedIds(new Set())} size="icon" type="button" variant="ghost"><X className="h-4 w-4" /></Button>
            </div>
          </> : <span className="text-xs text-muted-foreground">选择项目后可统一归档、恢复或删除</span>}
        </div>
      ) : null}

      {errorMessage || projectsQuery.isError ? <p className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive" role="alert">{errorMessage ?? "项目列表读取失败，请检查生成服务连接。"}</p> : null}

      {projectsQuery.isPending ? (
        <div className="ops-panel flex min-h-52 items-center justify-center text-sm text-muted-foreground"><FolderKanban className="mr-2 h-5 w-5 animate-pulse" />正在调取项目档案…</div>
      ) : visibleProjects.length ? (
        <div className="project-grid" ref={gridRef}>
          {visibleProjects.map((project) => (
            <ProjectCard
              key={project.id}
              onArchive={(item) => animateMutation(item.id, () => updateMutation.mutate({ id: item.id, payload: { status: "archived", archived_at: new Date().toISOString() } }), statusFilter !== "archived")}
              onContinue={onContinue}
              onDelete={(item) => { if (window.confirm(`软删除项目“${item.title}”？媒体文件仍会保留。`)) animateMutation(item.id, () => deleteMutation.mutate(item.id), true); }}
              onOpen={onOpenProject}
              onRename={(id, title) => updateMutation.mutate({ id, payload: { title } })}
              onSelectedChange={toggleProject}
              project={(() => {
                const jobs = jobsForProject(project.id);
                const latestJob = jobs[0];
                if (!latestJob) return project;
                const latestVideoJob = jobs.find((job) => job.job_type === "video_generation");
                const storyboardJob = jobs.find((job) => job.job_type === "storyboard_generation" && job.status === "completed");
                const prompts = storyboardJob?.result_json.image_prompts;
                const statusJob = latestVideoJob ?? latestJob;
                return {
                  ...project,
                  storyboardCount: Math.max(project.storyboardCount, Array.isArray(prompts) ? prompts.length : 0),
                  latestJobId: statusJob.id,
                  latestJobStatus: statusJob.status === "completed" ? "success" : statusJob.status === "pending" ? "queued" : statusJob.status,
                  latestJobType: statusJob.job_type,
                  latestJobProgress: statusJob.progress,
                  latestJobCurrentScene: statusJob.progress_current_scene ?? null,
                  latestJobTotalScenes: statusJob.progress_total_scenes ?? null,
                };
              })()}
              selected={selectedIds.has(project.id)}
            />
          ))}
        </div>
      ) : (
        <div className="ops-panel flex min-h-52 flex-col items-center justify-center p-8 text-center"><Archive className="mb-3 h-7 w-7 text-muted-foreground" /><p className="font-display text-lg">没有符合条件的项目</p><p className="mt-1 text-sm text-muted-foreground">调整搜索或状态筛选，或建立第一个项目档案。</p></div>
      )}
      </div>
    </OperationsShell>
  );
}
