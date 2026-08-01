import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface FadeContentProps {
  children: ReactNode;
  className?: string;
  role?: string;
}

export function FadeContent({ children, className, role }: FadeContentProps) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      animate={{ opacity: 1, y: 0 }}
      className={cn(className)}
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      role={role}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
