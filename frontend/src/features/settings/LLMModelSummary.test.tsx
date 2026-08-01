import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LLMModelSummary } from "@/features/settings/LLMModelSummary";

describe("LLM model summary", () => {
  it("shows the current model and opens settings without rendering the config form", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ has_api_key: true, api_key_masked: "sk-****", base_url: "https://api.deepseek.com", model: "deepseek-chat" }), { status: 200, headers: { "Content-Type": "application/json" } })));
    const onOpenSettings = vi.fn();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><LLMModelSummary onOpenSettings={onOpenSettings} /></QueryClientProvider>);

    expect(await screen.findByText("deepseek-chat")).toBeInTheDocument();
    expect(screen.queryByLabelText("API Key")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "前往设置" }));
    expect(onOpenSettings).toHaveBeenCalledOnce();
  });
});
