import { cn } from "@/lib/utils";

interface ShinyTextProps {
  children: string;
  className?: string;
}

export function ShinyText({ children, className }: ShinyTextProps) {
  return (
    <span className={cn("rb-shiny-text inline-block", className)}>
      {children}
    </span>
  );
}
