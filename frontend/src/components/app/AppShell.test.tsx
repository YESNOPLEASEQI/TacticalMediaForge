import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { vi, describe, expect, it } from "vitest";
import { AppShell } from "@/components/app/AppShell";
import { OperationsShell } from "@/components/operations/OperationsShell";

describe("persistent app shell", () => {
  it("keeps the tactical background outside the animated route content", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <AppShell activeProjectId={null} contentKey="projects" onNavigate={() => undefined}>
          <OperationsShell><div>内容</div></OperationsShell>
        </AppShell>
      </QueryClientProvider>,
    );
    const shell = container.querySelector(".app-shell");
    const routeContent = container.querySelector(".app-shell__content");
    expect(shell?.querySelectorAll(".rb-tactical-grid")).toHaveLength(1);
    expect(routeContent?.querySelector(".rb-tactical-grid")).toBeNull();
  });

  it("shows the project sidebar without a history navigation entry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <AppShell activeProjectId={null} onNavigate={() => undefined}><main>内容</main></AppShell>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("button", { name: /新建项目/ })).toBeInTheDocument();
    expect(screen.getByText("所有项目")).toBeInTheDocument();
    expect(screen.queryByText("历史记录")).not.toBeInTheDocument();
    expect(screen.queryByTestId("sidebar-active-indicator")).not.toBeInTheDocument();
  });

  it("opens a dedicated inline project form instead of a browser prompt", async () => {
    const prompt = vi.spyOn(window, "prompt");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <AppShell activeProjectId={null} onNavigate={() => undefined}><main>内容</main></AppShell>
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "新建项目" }));

    expect(screen.getByText("建立项目档案")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("例如：远程预警体系")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("选题、受众或交付目标")).toBeInTheDocument();
    expect(prompt).not.toHaveBeenCalled();
  });
});
