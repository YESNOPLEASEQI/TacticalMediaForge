import * as React from "react";
import { cn } from "@/lib/utils";

interface Spark {
  id: number;
  x: number;
  y: number;
}

interface ClickSparkProps {
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
}

export function ClickSpark({ children, className, disabled = false }: ClickSparkProps) {
  const [sparks, setSparks] = React.useState<Spark[]>([]);
  const idRef = React.useRef(0);

  function handleClick(event: React.MouseEvent<HTMLDivElement>) {
    if (disabled || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const rect = event.currentTarget.getBoundingClientRect();
    const id = idRef.current++;
    const spark = {
      id,
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };

    setSparks((current) => [...current, spark]);
    window.setTimeout(() => {
      setSparks((current) => current.filter((item) => item.id !== id));
    }, 520);
  }

  return (
    <div className={cn("relative", className)} onClick={handleClick}>
      {children}
      <span aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden rounded-md">
        {sparks.map((spark) => (
          <span
            className="rb-click-spark"
            key={spark.id}
            style={{ left: spark.x, top: spark.y }}
          />
        ))}
      </span>
    </div>
  );
}
