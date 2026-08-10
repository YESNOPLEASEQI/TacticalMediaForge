import { Check, Clapperboard, FileText, Film } from "lucide-react";
import Stepper, { Step } from "@/components/Stepper";
import { cn } from "@/lib/utils";
import type { WorkflowStage } from "@/features/video/workflow";

interface WorkflowStepNavProps {
  stage: WorkflowStage;
  scriptConfirmed: boolean;
  storyboardConfirmed: boolean;
  onChange: (stage: WorkflowStage) => void;
}

const steps = [
  { id: "script", label: "脚本", icon: FileText },
  { id: "storyboard", label: "分镜", icon: Clapperboard },
  { id: "video", label: "视频", icon: Film },
] as const;

export function WorkflowStepNav({
  stage,
  scriptConfirmed,
  storyboardConfirmed,
  onChange,
}: WorkflowStepNavProps) {
  const completed = { script: scriptConfirmed, storyboard: storyboardConfirmed, video: false };
  const enabled = { script: true, storyboard: scriptConfirmed, video: scriptConfirmed && storyboardConfirmed };
  const currentStep = steps.findIndex((step) => step.id === stage) + 1;

  return (
    <nav aria-label="视频生成步骤" className="workflow-stepper-shell">
      <Stepper
        className="!block !min-h-0 !p-0 sm:!aspect-auto md:!aspect-auto"
        currentStep={currentStep}
        onStepChange={(stepNumber) => {
          const next = steps[stepNumber - 1];
          if (next && enabled[next.id]) onChange(next.id);
        }}
        renderStepIndicator={({ step, onStepClick }) => {
          const definition = steps[step - 1];
          const Icon = definition.icon;
          const isActive = definition.id === stage;
          const isComplete = completed[definition.id];
          return (
            <button
              aria-current={isActive ? "step" : undefined}
              className={cn("workflow-step", isActive && "is-active", isComplete && "is-complete")}
              data-active={isActive ? "true" : "false"}
              data-workflow-step={definition.id}
              disabled={!enabled[definition.id]}
              onClick={() => onStepClick(step)}
              type="button"
            >
              <span className="workflow-step__marker">
                {isComplete && !isActive ? <Check className="h-4 w-4" aria-hidden="true" /> : <Icon className="h-4 w-4" aria-hidden="true" />}
              </span>
              <span className="font-display text-sm font-semibold">{definition.label}</span>
            </button>
          );
        }}
        showContent={false}
        showFooter={false}
        stepCircleContainerClassName="!max-w-none !rounded-md !border-border/80 !bg-card/80 !shadow-none"
        stepContainerClassName="!p-2"
      >
        {steps.map((step) => <Step key={step.id}><span>{step.label}</span></Step>)}
      </Stepper>
    </nav>
  );
}
