import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS class names, resolving conflicting utility classes
 * (via `tailwind-merge`) after combining conditional class values (via `clsx`).
 *
 * This is the standard shadcn/ui-style `cn()` helper used throughout the
 * `components/ui/*` primitives to allow callers to override default styling.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
