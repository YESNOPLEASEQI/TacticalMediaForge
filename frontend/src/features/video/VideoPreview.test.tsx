import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VideoPreview } from "@/features/video/VideoPreview";

describe("VideoPreview", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("pauses the inline player before opening the enlarged preview", () => {
    const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    render(<VideoPreview src="/preview.mp4" />);

    fireEvent.click(screen.getByRole("button", { name: "放大预览" }));

    expect(pause).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog", { name: "全屏视频预览" })).toBeInTheDocument();
  });
});
