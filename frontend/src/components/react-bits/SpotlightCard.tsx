import * as React from "react";
import { cn } from "@/lib/utils";

interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function SpotlightCard({ children, className, ...props }: SpotlightCardProps) {
  return (
    <div className={cn("rb-spotlight-card relative rounded-lg", className)} {...props}>
      {children}
    </div>
  );
}
