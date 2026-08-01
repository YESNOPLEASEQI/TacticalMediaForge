import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

interface AnimatedListProps {
  activeIndex: number;
  items: string[];
}

export function AnimatedList({ activeIndex, items }: AnimatedListProps) {
  const reduceMotion = useReducedMotion();

  return (
    <ol className="space-y-2">
      {items.map((item, index) => (
        <motion.li
          animate={{ opacity: index <= activeIndex ? 1 : 0.45, x: 0 }}
          className={cn(
            "flex items-center gap-3 rounded-md border border-border/70 bg-background/35 px-3 py-2 text-xs text-muted-foreground",
            index === activeIndex && "border-primary/60 bg-primary/8 text-foreground",
          )}
          initial={reduceMotion ? false : { opacity: 0, x: -8 }}
          key={item}
          transition={{ delay: reduceMotion ? 0 : index * 0.04, duration: 0.28 }}
        >
          <span className="font-data text-[10px] text-primary/80">{String(index + 1).padStart(2, "0")}</span>
          <span>{item}</span>
        </motion.li>
      ))}
    </ol>
  );
}
