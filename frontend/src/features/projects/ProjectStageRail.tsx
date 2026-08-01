import { Check, FileText, Film, PanelsTopLeft } from "lucide-react";
import Stepper, { Step } from "@/components/Stepper";
import { cn } from "@/lib/utils";

interface ProjectStageRailProps {
  currentStage?: string | null;
  hasScript: boolean;
  hasStoryboard: boolean;
  hasVideo: boolean;
  compact?: boolean;
}

const stages = [
  { id: "script", label: "脚本", icon: FileText },
  { id: "storyboard", label: "分镜", icon: PanelsTopLeft },
  { id: "video", label: "视频", icon: Film },
] as const;

export function ProjectStageRail({
  currentStage,
  hasScript,
  hasStoryboard,
  hasVideo,
  compact = false,
}: ProjectStageRailProps) {
  const complete = [hasScript, hasStoryboard, hasVideo];
  const activeIndex = currentStage === "storyboard" ? 1 : currentStage === "video" || currentStage === "output" ? 2 : 0;

  return (
    <Stepper
      aria-label="项目阶段进度"
      className="project-stage-stepper !block !min-h-0 !p-0 sm:!aspect-auto md:!aspect-auto"
      currentStep={activeIndex + 1}
      disableStepIndicators
      renderStepIndicator={({ step }) => {
        const index = step - 1;
        const stage = stages[index];
        const Icon = stage.icon;
        const isActive = index === activeIndex;
        const isComplete = complete[index];
        return (
          <span
            aria-current={isActive ? "step" : undefined}
            className={cn("project-stage-stepper__step", compact && "is-compact", isActive && "is-active", isComplete && "is-complete")}
          >
            <span className="project-stage-stepper__marker">
              {isComplete ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Icon className="h-3.5 w-3.5" aria-hidden="true" />}
            </span>
            <span>{stage.label}</span>
          </span>
        );
      }}
      showContent={false}
      showFooter={false}
      stepCircleContainerClassName="!max-w-none !rounded-none !border-0 !shadow-none"
      stepContainerClassName="!p-0"
    >
      {stages.map((stage) => <Step key={stage.id}><span>{stage.label}</span></Step>)}
    </Stepper>
  );
}
