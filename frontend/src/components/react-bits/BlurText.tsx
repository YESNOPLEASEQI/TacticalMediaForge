import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

interface BlurTextProps {
  children: string;
  className?: string;
}

export function BlurText({ children, className }: BlurTextProps) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.p
      animate={{ opacity: 1, filter: "blur(0px)", y: 0 }}
      className={cn("text-sm text-muted-foreground", className)}
      initial={reduceMotion ? false : { opacity: 0, filter: "blur(8px)", y: 6 }}
      transition={{ duration: 0.55, ease: "easeOut" }}
    >
      {children}
    </motion.p>
  );
}
