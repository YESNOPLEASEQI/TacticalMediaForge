import * as ToastPrimitive from "@radix-ui/react-toast";
import { X } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return (
    <ToastPrimitive.Provider swipeDirection="right">
      {toasts.map((toast) => (
        <ToastPrimitive.Root
          key={toast.id}
          className={cn(
            "grid w-full gap-1 rounded-md border bg-card p-4 text-card-foreground data-[state=open]:animate-in data-[state=closed]:animate-out sm:min-w-[360px]",
            toast.variant === "destructive" && "border-destructive/50",
          )}
          onOpenChange={(open) => {
            if (!open) {
              dismiss(toast.id);
            }
          }}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <ToastPrimitive.Title className="text-sm font-semibold">{toast.title}</ToastPrimitive.Title>
              {toast.description && (
                <ToastPrimitive.Description className="mt-1 text-sm text-muted-foreground">
                  {toast.description}
                </ToastPrimitive.Description>
              )}
            </div>
            <ToastPrimitive.Close className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
              <X className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">Close</span>
            </ToastPrimitive.Close>
          </div>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport className="fixed right-4 top-4 z-50 flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2 outline-none" />
    </ToastPrimitive.Provider>
  );
}
