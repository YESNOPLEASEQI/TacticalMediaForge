import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app/AppShell";
import { projectQueries } from "@/api/projects";
import { ProjectCenterPage } from "@/features/projects/ProjectCenterPage";
import { ProjectDetailPage } from "@/features/projects/ProjectDetailPage";
import { VideoGeneratorPage } from "@/features/video/VideoGeneratorPage";
import { SettingsPage } from "@/features/settings/SettingsPage";

export type AppRoute =
  | { view: "projects" }
  | { view: "project"; projectId: string }
  | { view: "generate"; projectId: string | null; sessionId: string | null }
  | { view: "settings" };

export function routeFromHash(source = window.location.hash): AppRoute {
  const hash = source.replace(/^#/, "");
  if (!hash || hash === "projects") return { view: "projects" };
  if (hash === "history") return { view: "projects" };
  if (hash === "settings") return { view: "settings" };
  if (hash.startsWith("projects/")) {
    return {
      view: "project",
      projectId: decodeURIComponent(hash.slice("projects/".length)),
    };
  }
  if (hash.startsWith("generate/project/")) {
    return {
      view: "generate",
      projectId: decodeURIComponent(hash.slice("generate/project/".length)),
      sessionId: null,
    };
  }
  if (hash.startsWith("generate/")) {
    return {
      view: "generate",
      projectId: null,
      sessionId: decodeURIComponent(hash.slice("generate/".length)),
    };
  }
  if (hash === "generate")
    return { view: "generate", projectId: null, sessionId: null };
  return { view: "projects" };
}

export function hashForRoute(route: AppRoute): string {
  if (route.view === "projects") return "projects";
  if (route.view === "project")
    return `projects/${encodeURIComponent(route.projectId)}`;
  if (route.view === "settings") return "settings";
  if (route.projectId)
    return `generate/project/${encodeURIComponent(route.projectId)}`;
  return route.sessionId
    ? `generate/${encodeURIComponent(route.sessionId)}`
    : "generate";
}

export default function App() {
  const [route, setRoute] = React.useState<AppRoute>(routeFromHash);

  React.useEffect(() => {
    const onHashChange = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = (next: AppRoute) => {
    window.location.hash = hashForRoute(next);
    setRoute(next);
  };

  const activeProjectId = route.view === "project" || route.view === "generate" ? route.projectId : null;
  let content: React.ReactNode;
  if (route.view === "projects") {
    content = (
      <ProjectCenterPage
        onContinue={(projectId) =>
          navigate({ view: "generate", projectId, sessionId: null })
        }
        onOpenProject={(projectId) => navigate({ view: "project", projectId })}
      />
    );
  } else if (route.view === "project") {
    content = (
      <ProjectDetailPage
        onBack={() => navigate({ view: "projects" })}
        onContinue={() =>
          navigate({
            view: "generate",
            projectId: route.projectId,
            sessionId: null,
          })
        }
        projectId={route.projectId}
      />
    );
  } else if (route.view === "generate" && route.projectId) {
    content = (
      <VideoGeneratorPage
        key={route.projectId}
        onOpenProjects={() => navigate({ view: "projects" })}
        onOpenSettings={() => navigate({ view: "settings" })}
        projectId={route.projectId}
      />
    );
  } else if (route.view === "generate" && route.sessionId) {
    content = <LegacySessionRedirect onResolved={(projectId) => navigate(projectId ? { view: "generate", projectId, sessionId: null } : { view: "projects" })} sessionId={route.sessionId} />;
  } else if (route.view === "settings") {
    content = <SettingsPage />;
  } else {
    content = <ProjectCenterPage onContinue={(projectId) => navigate({ view: "generate", projectId, sessionId: null })} onOpenProject={(projectId) => navigate({ view: "project", projectId })} />;
  }
  const contentKey = route.view === "project"
    ? `project:${route.projectId}`
    : route.view === "generate"
      ? `generate:${route.projectId ?? route.sessionId ?? "new"}`
      : route.view;
  return <AppShell activeProjectId={activeProjectId} contentKey={contentKey} onNavigate={(hash) => navigate(routeFromHash(`#${hash}`))}>{content}</AppShell>;
}

function LegacySessionRedirect({ sessionId, onResolved }: { sessionId: string; onResolved: (projectId: string | null) => void }) {
  const projectsQuery = useQuery(projectQueries.all());
  React.useEffect(() => {
    if (!projectsQuery.data) return;
    const project = projectsQuery.data.find((item) => item.id === sessionId || item.session?.id === sessionId);
    onResolved(project?.id ?? null);
  }, [onResolved, projectsQuery.data, sessionId]);
  return <div className="p-6 text-sm text-muted-foreground">正在关联旧项目记录…</div>;
}
