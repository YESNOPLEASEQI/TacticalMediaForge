import { Globe2, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

interface GenerationModeSelectorProps {
  mode: "reference" | "quick";
  capabilityEnabled: boolean;
  disabled?: boolean;
  ariaLabel: string;
  onChange: (mode: "reference" | "quick") => void;
}

export function GenerationModeSelector({
  mode,
  capabilityEnabled,
  disabled = false,
  ariaLabel,
  onChange,
}: GenerationModeSelectorProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2" aria-label={ariaLabel}>
      <Button
        aria-pressed={mode === "reference"}
        className="h-auto justify-start gap-3 p-4 text-left"
        disabled={disabled || !capabilityEnabled}
        onClick={() => onChange("reference")}
        type="button"
        variant={mode === "reference" ? "default" : "secondary"}
      >
        <Globe2 className="h-5 w-5 shrink-0" />
        <span className="font-medium">联网事实增强</span>
      </Button>
      <Button
        aria-pressed={mode === "quick"}
        className="h-auto justify-start gap-3 p-4 text-left"
        disabled={disabled}
        onClick={() => onChange("quick")}
        type="button"
        variant={mode === "quick" ? "default" : "secondary"}
      >
        <Zap className="h-5 w-5 shrink-0" />
        <span className="font-medium">快速生成</span>
      </Button>
    </div>
  );
}

interface ResearchModeSelectorProps {
  mode: "verified" | "quick";
  capabilityEnabled: boolean;
  disabled?: boolean;
  onChange: (mode: "verified" | "quick") => void;
}

export function ResearchModeSelector(props: ResearchModeSelectorProps) {
  return (
    <GenerationModeSelector
      ariaLabel="分镜生成依据"
      capabilityEnabled={props.capabilityEnabled}
      disabled={props.disabled}
      mode={props.mode === "verified" ? "reference" : "quick"}
      onChange={(mode) => props.onChange(mode === "reference" ? "verified" : "quick")}
    />
  );
}
