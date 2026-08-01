import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, KeyRound, RefreshCw, Save } from "lucide-react";
import { fetchLLMModels, llmQueries, saveLLMConfig } from "@/api/llm";
import { FadeContent } from "@/components/react-bits/FadeContent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

const fallbackModels = ["deepseek-chat", "deepseek-reasoner"];
const deepSeekBaseUrl = "https://api.deepseek.com";

export function LLMConfigPanel() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const configQuery = useQuery(llmQueries.config());
  const [isOpen, setIsOpen] = React.useState(false);
  const [apiKey, setApiKey] = React.useState("");
  const [baseUrl, setBaseUrl] = React.useState(deepSeekBaseUrl);
  const [model, setModel] = React.useState("deepseek-chat");
  const [models, setModels] = React.useState(fallbackModels);

  React.useEffect(() => {
    if (!configQuery.data) {
      return;
    }

    setBaseUrl(configQuery.data.base_url || deepSeekBaseUrl);
    setModel(configQuery.data.model || "deepseek-chat");
  }, [configQuery.data]);

  const modelsMutation = useMutation({
    mutationFn: fetchLLMModels,
    onSuccess: (response) => {
      const nextModels = response.models.length > 0 ? response.models : fallbackModels;
      setModels(nextModels);
      if (!nextModels.includes(model)) {
        setModel(nextModels[0]);
      }
      toast({
        title: "模型列表已更新",
        description: `发现 ${nextModels.length} 个模型。`,
      });
    },
    onError: (error) => {
      toast({
        title: "模型拉取失败",
        description: error instanceof Error ? error.message : "请检查 DeepSeek API Key 和 Base URL。",
        variant: "destructive",
      });
    },
  });

  const saveMutation = useMutation({
    mutationFn: saveLLMConfig,
    onSuccess: async (response) => {
      setApiKey("");
      setBaseUrl(response.base_url);
      setModel(response.model);
      setIsOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["llm", "config"] });
      toast({
        title: "语言模型配置已保存",
        description: `${response.model} / ${response.base_url}`,
      });
    },
    onError: (error) => {
      toast({
        title: "配置保存失败",
        description: error instanceof Error ? error.message : "无法保存语言模型配置。",
        variant: "destructive",
      });
    },
  });

  const configuredModel = configQuery.data?.model || model;
  const configuredBaseUrl = configQuery.data?.base_url || baseUrl;

  return (
    <section className="ops-panel overflow-hidden">
      <div className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-primary/35 bg-primary/10 text-primary">
            <KeyRound className="h-4 w-4" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-display text-sm font-semibold">语言模型配置</p>
              <Badge variant={configQuery.data?.has_api_key ? "success" : "warning"}>
                {configQuery.data?.has_api_key ? "Key 已配置" : "未配置 Key"}
              </Badge>
            </div>
            <p className="truncate text-xs text-muted-foreground">
              {configuredModel} / {configuredBaseUrl}
            </p>
          </div>
        </div>

        <Button
          aria-controls="llm-config-content"
          aria-expanded={isOpen}
          onClick={() => setIsOpen((current) => !current)}
          size="sm"
          type="button"
          variant="secondary"
        >
          {isOpen ? "收起配置" : "配置模型"}
          <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} aria-hidden="true" />
        </Button>
      </div>

      <AnimatePresence initial={false}>
        {isOpen ? (
          <motion.div
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            id="llm-config-content"
            initial={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <FadeContent className="border-t border-border/70 p-4">
              <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
                <div className="space-y-2">
                  <label className="control-label" htmlFor="llm_base_url">
                    Base URL
                  </label>
                  <Input
                    id="llm_base_url"
                    onChange={(event) => setBaseUrl(event.target.value)}
                    placeholder={deepSeekBaseUrl}
                    value={baseUrl}
                  />
                </div>
                <div className="space-y-2">
                  <label className="control-label" htmlFor="llm_api_key">
                    API Key
                  </label>
                  <Input
                    id="llm_api_key"
                    onChange={(event) => setApiKey(event.target.value)}
                    placeholder={configQuery.data?.api_key_masked || "输入新的 DeepSeek API Key"}
                    type="password"
                    value={apiKey}
                  />
                  <p className="control-help">留空保存时保留当前 Key；输入新 Key 才会覆盖。</p>
                </div>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_auto_auto]">
                <div className="space-y-2">
                  <label className="control-label" htmlFor="llm_model">
                    模型
                  </label>
                  <Select onValueChange={setModel} value={model}>
                    <SelectTrigger id="llm_model">
                      <SelectValue placeholder="选择模型" />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map((item) => (
                        <SelectItem key={item} value={item}>
                          {item}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  className="self-end"
                  isLoading={modelsMutation.isPending}
                  onClick={() => modelsMutation.mutate({ api_key: apiKey || null, base_url: baseUrl })}
                  type="button"
                  variant="secondary"
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  拉取模型
                </Button>
                <Button
                  className="self-end"
                  isLoading={saveMutation.isPending}
                  onClick={() => saveMutation.mutate({ api_key: apiKey || null, base_url: baseUrl, model })}
                  type="button"
                >
                  <Save className="h-4 w-4" aria-hidden="true" />
                  保存配置
                </Button>
              </div>
            </FadeContent>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}
