import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/hooks/use-toast";
import { SettingsPage } from "@/features/settings/SettingsPage";

afterEach(() => vi.unstubAllGlobals());

function response(payload: unknown) {
  return Promise.resolve(new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }));
}

describe("settings page", () => {
  it("contains only LLM configuration, generation resources and application information", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/llm/config")) return response({ has_api_key: true, api_key_masked: "sk-****", base_url: "https://api.deepseek.com", model: "deepseek-chat" });
      if (url.endsWith("/health")) return response({ status: "healthy", version: "0.1.0" });
      if (url.includes("workflows/media")) return response({ workflows: [{ key: "media-a" }, { key: "media-b" }] });
      if (url.includes("workflows/tts")) return response({ workflows: [{ key: "tts-a" }] });
      if (url.endsWith("/templates")) return response({ templates: [{ key: "template-a" }] });
      if (url.endsWith("/bgm")) return response({ bgm_files: [{ name: "bgm-a" }] });
      return response({});
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(<QueryClientProvider client={client}><ToastProvider><SettingsPage /></ToastProvider></QueryClientProvider>);

    expect(await screen.findByRole("heading", { name: "设置" })).toBeInTheDocument();
    expect(screen.getByText("语言模型配置")).toBeInTheDocument();
    expect(screen.getByText("生成资源状态")).toBeInTheDocument();
    expect(screen.getByText("应用信息")).toBeInTheDocument();
    expect(await screen.findByText("2")).toBeInTheDocument();
    expect(screen.queryByText(/备份|清理|通知|自动切换/)).not.toBeInTheDocument();
  });
});
