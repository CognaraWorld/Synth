"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useMeetings } from "@/hooks/use-meetings";

export function StartMeetingDialog() {
  const [open, setOpen] = useState(false);
  const [joinUrl, setJoinUrl] = useState("");
  const { createMeeting, isCreating } = useMeetings();

  async function handleSubmit() {
    if (!joinUrl) return;
    await createMeeting({ joinUrl });
    setJoinUrl("");
    setOpen(false);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4" />
          Start a Meeting
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Start a Meeting</DialogTitle>
          <DialogDescription>Paste a meeting link and your bot will join immediately.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="join-url">Meeting link</Label>
            <Input
              id="join-url"
              value={joinUrl}
              onChange={(e) => setJoinUrl(e.target.value)}
              placeholder="https://meet.google.com/... or https://zoom.us/j/..."
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSubmit();
              }}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!joinUrl || isCreating}>
            {isCreating ? "Joining..." : "Join Meeting"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
