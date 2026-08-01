import * as React from "react";
import { ArrowLeft, Boxes, Clapperboard, FileText, Film, LayoutDashboard, ListVideo, Play } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { projectQueries } from "@/api/projects";
import { OperationsShell, WorkbenchHeader } from "@/components/operations/OperationsShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ProjectDetailSection, type ProjectDetailTab } from "@/features/projects/ProjectDetailSections";
import { ProjectOverview } from "@/features/projects/ProjectOverview";
import { projectStageLabel, projectStatusLabel, projectStatusVariant } from "@/features/projects/projectFormat";
import { gsap, useGSAP } from "@/lib/gsap";
import { cn } from "@/lib/utils";

interface ProjectDetailPageProps {
  onBack: () => void;
  onContinue: (projectId: string) => void;
  projectId: string;
}

const tabs = [
  { id: "overview", label: "概览", icon: LayoutDashboard },
  { id: "script", label: "脚本", icon: FileText },
  { id: "storyboard", label: "分镜", icon: Clapperboard },
  { id: "assets", label: "资产", icon: Boxes },
  { id: "jobs", label: "生成记录", icon: ListVideo },
  { id: "outputs", label: "成片", icon: Film },
] satisfies Array<{ id: ProjectDetailTab; label: string; icon: typeof LayoutDashboard }>;

export function ProjectDetailPage({ onBack, onContinue, projectId }: ProjectDetailPageProps) {
  const [tab, setTab] = React.useState<ProjectDetailTab>("overview");
  const pageRef = React.useRef<HTMLDivElement>(null);
  const panelRef = React.useRef<HTMLDivElement>(null);
  const workspaceQuery = useQuery(projectQueries.workspace(projectId));
  const workspace = workspaceQuery.data;

  useGSAP(() => {
    if (!workspace || !panelRef.current) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    gsap.fromTo(panelRef.current, { autoAlpha: 0, x: reduced ? 0 : 14, scale: reduced ? 1 : 0.995 }, { autoAlpha: 1, x: 0, scale: 1, duration: reduced ? 0.18 : 0.42, ease: "reveal", overwrite: "auto", clearProps: "transform,opacity,visibility" });
  }, { scope: pageRef, dependencies: [tab, Boolean(workspace)], revertOnUpdate: true });

  if (workspaceQuery.isPending) {
    return <OperationsShell><div className="ops-panel flex min-h-72 items-center justify-center text-sm text-muted-foreground"><LayoutDashboard className="mr-2 h-5 w-5 animate-pulse" />正在加载项目内容…</div></OperationsShell>;
  }

  if (!workspace || workspaceQuery.isError) {
    return <OperationsShell><div className="ops-panel p-6"><p className="text-destructive" role="alert">项目详情读取失败。</p><Button className="mt-4" onClick={onBack} type="button" variant="secondary"><ArrowLeft className="h-4 w-4" />返回项目中心</Button></div></OperationsShell>;
  }

  const { project } = workspace;
  return (
    <OperationsShell>
      <div ref={pageRef}>
      <WorkbenchHeader
        actions={<><Button onClick={onBack} size="sm" type="button" variant="secondary"><ArrowLeft className="h-4 w-4" />项目中心</Button><Button disabled={project.status === "archived"} onClick={() => onContinue(project.id)} size="sm" type="button"><Play className="h-4 w-4" />继续创作 · {projectStageLabel(project.current_stage)}</Button></>}
        meta={<><Badge variant={projectStatusVariant(project.status)}>{projectStatusLabel(project.status)}</Badge><Badge variant="outline">{projectStageLabel(project.current_stage)}</Badge></>}
        summary={project.description ?? undefined}
        title={project.title}
      />

      <nav aria-label="项目详情" className="ops-panel mb-4 flex gap-1 overflow-x-auto p-1" role="tablist">
        {tabs.map((item) => {
          const Icon = item.icon;
          return <button aria-selected={tab === item.id} className={cn("flex min-w-max items-center gap-2 rounded-sm px-4 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground", tab === item.id && "bg-primary/12 text-primary")} key={item.id} onClick={() => setTab(item.id)} role="tab" type="button"><Icon className="h-4 w-4" aria-hidden="true" />{item.label}</button>;
        })}
      </nav>

      <div data-project-tab={tab} ref={panelRef} role="tabpanel">
        {tab === "overview" ? <ProjectOverview workspace={workspace} /> : <ProjectDetailSection tab={tab} workspace={workspace} />}
      </div>
      </div>
    </OperationsShell>
  );
}
