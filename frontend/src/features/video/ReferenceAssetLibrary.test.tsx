import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReferenceAssetLibrary } from "@/features/video/ReferenceAssetLibrary";
import type { ReferenceAsset } from "@/types/api";

const asset: ReferenceAsset = {
  id: "asset-1",
  project_id: "project-1",
  filename: "radar.webp",
  mime_type: "image/webp",
  size_bytes: 1024,
  width: 640,
  height: 360,
  metadata_json: {},
  url: "/radar.webp",
  created_at: "2026-08-10T00:00:00Z",
};

const callbacks = {
  onApplyAll: vi.fn(),
  onClearAll: vi.fn(),
  onDelete: vi.fn(),
  onUpload: vi.fn(),
};

afterEach(() => vi.restoreAllMocks());

describe("equipment reference library", () => {
  it("explains the impact before deleting an in-use reference", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const onDelete = vi.fn();
    render(<ReferenceAssetLibrary {...callbacks} assets={[asset]} boundSceneCount={1} onDelete={onDelete} usageCounts={{ "asset-1": 2 }} />);

    fireEvent.click(screen.getByRole("button", { name: "删除 radar.webp" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("当前有 2 个分镜正在使用"));
    expect(onDelete).toHaveBeenCalledWith("asset-1");
  });

  it("reports a completed upload when the loading state settles", () => {
    const { rerender } = render(<ReferenceAssetLibrary {...callbacks} assets={[]} isUploading />);
    rerender(<ReferenceAssetLibrary {...callbacks} assets={[asset]} isUploading={false} />);

    expect(screen.getByRole("status")).toHaveTextContent("上传成功，已加入装备视觉参考");
  });
});
