import { Bell, Search } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface TopbarProps {
  userName?: string | null;
}

export function Topbar({ userName }: TopbarProps) {
  const displayName = userName ?? "Demo User";

  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/80 px-4 py-4 backdrop-blur lg:px-8">
      <div className="flex items-center gap-3">
        <div className="relative hidden max-w-md flex-1 lg:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-10" placeholder="Search meetings, reports, documents..." />
        </div>
        <div className="ml-auto flex items-center gap-3">
          <Button size="icon" variant="outline">
            <Bell className="h-4 w-4" />
          </Button>
          <ThemeToggle />
          <div className="flex items-center gap-3 rounded-2xl border border-border/70 bg-card/70 px-3 py-2">
            <Avatar>
              <AvatarFallback name={displayName} />
            </Avatar>
            <div className="hidden sm:block">
              <p className="text-sm font-medium">{displayName}</p>
              <p className="text-xs text-muted-foreground">Meeting Bot</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
