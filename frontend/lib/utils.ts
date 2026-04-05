import { clsx, type ClassValue } from "clsx";
import { format, formatDistanceToNow, isToday, isTomorrow } from "date-fns";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMeetingTime(value: string) {
  const date = new Date(value);

  if (isToday(date)) {
    return `Today, ${format(date, "h:mm a")}`;
  }

  if (isTomorrow(date)) {
    return `Tomorrow, ${format(date, "h:mm a")}`;
  }

  return format(date, "EEE, MMM d • h:mm a");
}

export function formatRelativeDate(value: string) {
  return formatDistanceToNow(new Date(value), { addSuffix: true });
}

export function formatMinutes(minutes: number) {
  if (minutes < 60) {
    return `${minutes} min`;
  }

  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours}h ${remainder}m` : `${hours}h`;
}

export function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
