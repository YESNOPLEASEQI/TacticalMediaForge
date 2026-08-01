import type { ReactNode } from "react";
import { FadeContent } from "@/components/react-bits/FadeContent";
import { cn } from "@/lib/utils";

interface OperationsShellProps {
  children: ReactNode;
}

interface WorkbenchHeaderProps {
  actions?: ReactNode;
  eyebrow?: string;
  meta?: ReactNode;
  summary?: string;
  title: string;
}

interface StatusStripProps {
  items: Array<{
    label: string;
    value: ReactNode;
    tone?: "default" | "good" | "warn" | "bad";
  }>;
}

interface SectionPanelProps {
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  description?: string;
  eyebrow?: string;
  title?: string;
}

function toneClass(tone: "default" | "good" | "warn" | "bad" = "default") {
  if (tone === "good") {
    return "border-accent/50 text-accent";
  }
  if (tone === "warn") {
    return "border-amber-500/50 text-amber-300";
  }
  if (tone === "bad") {
    return "border-destructive/60 text-destructive-foreground";
  }
  return "border-border text-muted-foreground";
}

export function OperationsShell({ children }: OperationsShellProps) {
  return (
    <main className="ops-page">
      <div className="ops-container">{children}</div>
    </main>
  );
}

export function WorkbenchHeader({ actions, eyebrow, meta, summary, title }: WorkbenchHeaderProps) {
  return (
    <FadeContent>
      <header className="mb-5 border-b border-border/80 pb-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            {eyebrow || meta ? <div className="mb-2 flex flex-wrap items-center gap-3">
              {eyebrow ? <span className="ops-kicker">{eyebrow}</span> : null}
              {meta}
            </div> : null}
            <h1 className="ops-title">{title}</h1>
            {summary ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{summary}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      </header>
    </FadeContent>
  );
}

export function StatusStrip({ items }: StatusStripProps) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <div className={cn("rounded-md border bg-background/34 px-3 py-2", toneClass(item.tone))} data-motion="project-stat" key={item.label}>
          <p className="text-[11px] text-muted-foreground">{item.label}</p>
          <div className="mt-1 font-data text-sm text-foreground">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

export function SectionPanel({ actions, children, className, description, eyebrow, title }: SectionPanelProps) {
  return (
    <section className={cn("ops-panel", className)}>
      {title || description || actions ? (
        <div className="flex flex-col gap-3 border-b border-border/70 p-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            {eyebrow ? <p className="ops-kicker mb-1">{eyebrow}</p> : null}
            {title ? <h2 className="font-display text-lg font-semibold">{title}</h2> : null}
            {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
        </div>
      ) : null}
      <div className="p-4">{children}</div>
    </section>
  );
}
