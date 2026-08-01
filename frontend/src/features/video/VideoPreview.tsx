import * as React from "react";
import { createPortal } from "react-dom";
import { Maximize2, Pause, Play, RotateCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface VideoPreviewProps {
  className?: string;
  src: string;
}

interface VideoPlayerProps {
  aspectRatio: number;
  initialTime?: number;
  isLarge?: boolean;
  onAspectRatioChange?: (aspectRatio: number) => void;
  onExpand?: (currentTime: number) => void;
  onTimeChange?: (currentTime: number) => void;
  src: string;
  suspended?: boolean;
}

const defaultPortraitAspectRatio = 9 / 16;

function formatClock(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "0:00";
  }

  const minutes = Math.floor(seconds / 60);
  const remaining = Math.floor(seconds % 60);
  return `${minutes}:${remaining.toString().padStart(2, "0")}`;
}

function useViewportSize() {
  const [size, setSize] = React.useState(() => ({
    height: typeof window === "undefined" ? 800 : window.innerHeight,
    width: typeof window === "undefined" ? 1280 : window.innerWidth,
  }));

  React.useEffect(() => {
    const handleResize = () => {
      setSize({ height: window.innerHeight, width: window.innerWidth });
    };

    handleResize();
    window.addEventListener("resize", handleResize);

    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return size;
}

function getPlayerMaxWidth(aspectRatio: number, isLarge: boolean, viewport: { height: number; width: number }) {
  if (isLarge) {
    const maxVideoHeight = Math.max(120, viewport.height - 240);
    return Math.min(viewport.width * 0.92, maxVideoHeight * aspectRatio);
  }

  return Math.min(340, 540 * aspectRatio);
}

function VideoPlayer({
  aspectRatio,
  initialTime = 0,
  isLarge = false,
  onAspectRatioChange,
  onExpand,
  onTimeChange,
  src,
  suspended = false,
}: VideoPlayerProps) {
  const viewport = useViewportSize();
  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const hasAppliedInitialTime = React.useRef(false);
  const wasSuspended = React.useRef(suspended);
  const latestInitialTime = React.useRef(initialTime);
  const [currentTime, setCurrentTime] = React.useState(initialTime);
  const [duration, setDuration] = React.useState(0);
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [playbackError, setPlaybackError] = React.useState<string | null>(null);
  const maxWidth = getPlayerMaxWidth(aspectRatio, isLarge, viewport);
  latestInitialTime.current = initialTime;

  const updateTime = React.useCallback(
    (nextTime: number) => {
      setCurrentTime(nextTime);
      onTimeChange?.(nextTime);
    },
    [onTimeChange],
  );

  const togglePlayback = React.useCallback(async () => {
    const video = videoRef.current;
    if (!video) {
      return;
    }

    setPlaybackError(null);

    try {
      if (video.paused) {
        await video.play();
      } else {
        video.pause();
      }
    } catch (error) {
      setPlaybackError(error instanceof Error ? error.message : "无法启动视频播放");
    }
  }, []);

  const restart = React.useCallback(async () => {
    const video = videoRef.current;
    if (!video) {
      return;
    }

    video.currentTime = 0;
    updateTime(0);
    setPlaybackError(null);

    try {
      await video.play();
    } catch (error) {
      setPlaybackError(error instanceof Error ? error.message : "无法重新播放视频");
    }
  }, [updateTime]);

  const seek = React.useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const video = videoRef.current;
      const nextTime = Number(event.target.value);

      if (!video || !Number.isFinite(nextTime)) {
        return;
      }

      video.currentTime = nextTime;
      updateTime(nextTime);
    },
    [updateTime],
  );

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (suspended) {
      video.pause();
      setIsPlaying(false);
    } else if (wasSuspended.current) {
      video.currentTime = latestInitialTime.current;
      updateTime(latestInitialTime.current);
    }
    wasSuspended.current = suspended;
  }, [suspended, updateTime]);

  return (
    <div
      className={cn(
        "relative z-10 mx-auto overflow-hidden rounded-md border border-border bg-[#11120f]",
        isLarge && "border-primary/45",
      )}
      style={{ maxWidth, width: "100%" }}
    >
      <button
        aria-label={isPlaying ? "暂停视频" : "播放视频"}
        className="block w-full cursor-pointer bg-[#11120f] text-left"
        onClick={() => {
          void togglePlayback();
        }}
        type="button"
      >
        <video
          className="pointer-events-none block w-full bg-[#11120f] object-contain"
          onEnded={() => setIsPlaying(false)}
          onLoadedMetadata={(event) => {
            const video = event.currentTarget;
            const nextAspectRatio =
              video.videoWidth > 0 && video.videoHeight > 0
                ? video.videoWidth / video.videoHeight
                : defaultPortraitAspectRatio;

            onAspectRatioChange?.(nextAspectRatio);
            setDuration(video.duration || 0);

            if (!hasAppliedInitialTime.current && initialTime > 0) {
              video.currentTime = initialTime;
              updateTime(initialTime);
              hasAppliedInitialTime.current = true;
            }
          }}
          onPause={() => setIsPlaying(false)}
          onPlay={() => setIsPlaying(true)}
          onTimeUpdate={(event) => updateTime(event.currentTarget.currentTime)}
          playsInline
          preload="metadata"
          ref={videoRef}
          src={src}
          style={{ aspectRatio, maxHeight: isLarge ? Math.max(120, viewport.height - 240) : undefined }}
        >
          <track kind="captions" />
        </video>
      </button>

      <div className="space-y-3 border-t border-border bg-background/95 p-3">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            aria-label={isPlaying ? "暂停视频" : "播放视频"}
            onClick={() => {
              void togglePlayback();
            }}
            size="sm"
            type="button"
            variant="secondary"
          >
            {isPlaying ? <Pause className="h-4 w-4" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
            {isPlaying ? "暂停" : "播放"}
          </Button>
          <Button
            aria-label="重新播放视频"
            onClick={() => {
              void restart();
            }}
            size="sm"
            type="button"
            variant="ghost"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
          </Button>
          {onExpand ? (
            <Button aria-label="放大预览" onClick={() => onExpand(currentTime)} size="sm" type="button" variant="ghost">
              <Maximize2 className="h-4 w-4" aria-hidden="true" />
              放大预览
            </Button>
          ) : null}
          <span className="ml-auto min-w-[86px] font-data text-xs text-muted-foreground">
            {formatClock(currentTime)} / {formatClock(duration)}
          </span>
        </div>
        <input
          aria-label="视频进度"
          className="block h-2 w-full cursor-pointer accent-primary"
          max={duration || 0}
          min={0}
          onChange={seek}
          step="0.1"
          type="range"
          value={Math.min(currentTime, duration || currentTime)}
        />
        {playbackError ? <p className="text-xs text-destructive">{playbackError}</p> : null}
      </div>
    </div>
  );
}

function FullscreenPreview({
  aspectRatio,
  initialTime,
  onAspectRatioChange,
  onClose,
  onTimeChange,
  src,
}: {
  aspectRatio: number;
  initialTime: number;
  onAspectRatioChange: (aspectRatio: number) => void;
  onClose: () => void;
  onTimeChange: (currentTime: number) => void;
  src: string;
}) {
  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  return createPortal(
    <div
      aria-label="全屏视频预览"
      aria-modal="true"
      className="fixed inset-0 z-[100] flex flex-col overflow-y-auto overscroll-contain bg-background p-4 sm:p-6"
      role="dialog"
    >
      <div className="mb-4 flex items-center justify-between gap-4 border-b border-border pb-3">
        <div>
          <p className="ops-kicker">视频预览</p>
          <h2 className="mt-1 font-display text-lg font-semibold">全屏放大预览</h2>
        </div>
        <Button aria-label="退出全屏预览" onClick={onClose} type="button" variant="secondary">
          <X className="h-4 w-4" aria-hidden="true" />
          退出
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 items-center justify-center">
        <VideoPlayer
          aspectRatio={aspectRatio}
          initialTime={initialTime}
          isLarge
          onAspectRatioChange={onAspectRatioChange}
          onTimeChange={onTimeChange}
          src={src}
        />
      </div>
    </div>,
    document.body,
  );
}

export function VideoPreview({ className, src }: VideoPreviewProps) {
  const [aspectRatio, setAspectRatio] = React.useState(defaultPortraitAspectRatio);
  const [isFullscreenOpen, setIsFullscreenOpen] = React.useState(false);
  const [lastKnownTime, setLastKnownTime] = React.useState(0);

  return (
    <div className={className}>
      <VideoPlayer
        aspectRatio={aspectRatio}
        initialTime={lastKnownTime}
        onAspectRatioChange={setAspectRatio}
        onExpand={(currentTime) => {
          setLastKnownTime(currentTime);
          setIsFullscreenOpen(true);
        }}
        onTimeChange={setLastKnownTime}
        src={src}
        suspended={isFullscreenOpen}
      />
      {isFullscreenOpen ? (
        <FullscreenPreview
          aspectRatio={aspectRatio}
          initialTime={lastKnownTime}
          onAspectRatioChange={setAspectRatio}
          onClose={() => setIsFullscreenOpen(false)}
          onTimeChange={setLastKnownTime}
          src={src}
        />
      ) : null}
    </div>
  );
}
