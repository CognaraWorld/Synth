"use client";

import * as React from "react";
import * as AvatarPrimitive from "@radix-ui/react-avatar";
import { cn, initials } from "@/lib/utils";

export function Avatar(props: React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root>) {
  return <AvatarPrimitive.Root className={cn("relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full", props.className)} {...props} />;
}

export function AvatarImage(props: React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Image>) {
  return <AvatarPrimitive.Image className="aspect-square h-full w-full object-cover" {...props} />;
}

export function AvatarFallback({
  className,
  name = "User",
  ...props
}: React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback> & { name?: string }) {
  return (
    <AvatarPrimitive.Fallback
      className={cn("flex h-full w-full items-center justify-center bg-primary/15 text-sm font-semibold text-primary", className)}
      {...props}
    >
      {initials(name)}
    </AvatarPrimitive.Fallback>
  );
}
