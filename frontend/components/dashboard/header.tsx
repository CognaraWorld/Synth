import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { CreditCard } from "lucide-react";

export function Header() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-6">
      <div />
      <div className="flex items-center gap-4">
        <Badge variant="secondary" className="gap-1.5">
          <CreditCard className="size-3" />
          120 credits
        </Badge>
        <Separator orientation="vertical" className="h-6" />
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-sm font-medium leading-none">Yash Goel</p>
            <p className="text-xs text-muted-foreground">yash@synth.dev</p>
          </div>
          <Avatar className="size-8">
            <AvatarFallback className="text-xs">YG</AvatarFallback>
          </Avatar>
        </div>
      </div>
    </header>
  );
}
