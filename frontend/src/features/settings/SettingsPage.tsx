import { useQuery } from "@tanstack/react-query";
import { Activity, AppWindow, Boxes, FileCode2, Music2, Radio, Speech } from "lucide-react";
import { resourceQueries } from "@/api/resources";
import { OperationsShell, SectionPanel, WorkbenchHeader } from "@/components/operations/OperationsShell";
import { Badge } from "@/components/ui/badge";
import { LLMConfigPanel } from "@/features/settings/LLMConfigPanel";

function ResourceMetric({ icon: Icon, label, value, loading }: { icon: typeof Activity; label: string; value: string | number; loading?: boolean }) {
  return <div className="ops-panel-muted flex min-h-20 items-center gap-3 p-3"><Icon className="h-5 w-5 text-primary" aria-hidden="true" /><div><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-data text-lg">{loading ? "—" : value}</p></div></div>;
}

export function SettingsPage() {
  const healthQuery = useQuery(resourceQueries.health());
  const mediaQuery = useQuery(resourceQueries.mediaWorkflows());
  const ttsQuery = useQuery(resourceQueries.ttsWorkflows());
  const templatesQuery = useQuery(resourceQueries.templates());
  const bgmQuery = useQuery(resourceQueries.bgm());
  const apiOnline = healthQuery.isSuccess && healthQuery.data?.status !== "unhealthy";

  return <OperationsShell>
    <WorkbenchHeader
      meta={<Badge variant={apiOnline ? "success" : "destructive"}>{apiOnline ? "服务正常" : "生成服务未连接"}</Badge>}
      title="设置"
    />

    <div className="space-y-4">
      <LLMConfigPanel />

      <SectionPanel title="生成资源状态">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <ResourceMetric icon={Radio} label="API 状态" value={apiOnline ? "正常" : "未连接"} loading={healthQuery.isPending} />
          <ResourceMetric icon={Boxes} label="媒体工作流数量" value={mediaQuery.data?.workflows.length ?? 0} loading={mediaQuery.isPending} />
          <ResourceMetric icon={Speech} label="TTS 工作流数量" value={ttsQuery.data?.workflows.length ?? 0} loading={ttsQuery.isPending} />
          <ResourceMetric icon={FileCode2} label="模板数量" value={templatesQuery.data?.templates.length ?? 0} loading={templatesQuery.isPending} />
          <ResourceMetric icon={Music2} label="BGM 数量" value={bgmQuery.data?.bgm_files.length ?? 0} loading={bgmQuery.isPending} />
        </div>
      </SectionPanel>

      <SectionPanel title="应用信息">
        <dl className="grid gap-4 text-sm sm:grid-cols-3">
          <div><dt className="text-xs text-muted-foreground">应用</dt><dd className="mt-1 flex items-center gap-2"><AppWindow className="h-4 w-4 text-primary" />MilitaryVideoGenAgent</dd></div>
          <div><dt className="text-xs text-muted-foreground">版本</dt><dd className="mt-1 font-data">{String(healthQuery.data?.version ?? "0.1.0")}</dd></div>
          <div><dt className="text-xs text-muted-foreground">配置来源</dt><dd className="mt-1 font-data">config.yaml</dd></div>
        </dl>
      </SectionPanel>
    </div>
  </OperationsShell>;
}
