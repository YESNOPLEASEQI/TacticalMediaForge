import { motion } from "framer-motion";
import { Radar } from "lucide-react";
import { ClickSpark } from "@/components/react-bits/ClickSpark";
import { ElectricBorder } from "@/components/ElectricBorder";
import { Button } from "@/components/ui/button";

interface LaunchMissionButtonProps {
  disabled: boolean;
  isRunning: boolean;
  isSubmitting: boolean;
}

export function LaunchMissionButton({ disabled, isRunning, isSubmitting }: LaunchMissionButtonProps) {
  return (
    <ClickSpark disabled={disabled}>
      <ElectricBorder active={isRunning}>
        <motion.div whileHover={disabled ? undefined : { y: -1 }} whileTap={disabled ? undefined : { scale: 0.985 }}>
          <Button
            className="h-12 w-full rounded-md font-display text-base"
            disabled={disabled}
            isLoading={isSubmitting || isRunning}
            size="lg"
            type="submit"
          >
            <Radar className="h-5 w-5" aria-hidden="true" />
            {isRunning ? "任务执行中" : "启动生成任务"}
          </Button>
        </motion.div>
      </ElectricBorder>
    </ClickSpark>
  );
}
