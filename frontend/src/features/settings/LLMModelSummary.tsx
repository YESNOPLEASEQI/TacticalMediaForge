import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, BrainCircuit } from "lucide-react";
import { llmQueries } from "@/api/llm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function LLMModelSummary({ onOpenSettings }: { onOpenSettings: () => void }) {
  const configQuery = useQuery(llmQueries.config());
  return <div className="ops-panel-muted flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
    <div className="flex min-w-0 items-center gap-3">
      <BrainCircuit className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
      <div className="min-w-0"><p className="text-xs text-muted-foreground">当前语言模型</p><p className="truncate font-data text-sm">{configQuery.isPending ? "读取中…" : configQuery.data?.model || "未配置"}</p></div>
      <Badge variant={configQuery.data?.has_api_key ? "success" : "warning"}>{configQuery.data?.has_api_key ? "Key 已配置" : "未配置 Key"}</Badge>
    </div>
    <Button onClick={onOpenSettings} size="sm" type="button" variant="secondary">前往设置<ArrowUpRight className="h-4 w-4" /></Button>
  </div>;
}
