"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  ChevronDown,
  ChevronUp,
  Edit,
  FileText,
  Loader2,
  Plus,
  Trash2,
  Square,
  Upload,
  Video,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface Agent {
  id: string;
  name: string;
  description: string;
  mode: "general" | "custom";
  system_prompt?: string;
  created_at?: string;
}

interface Document {
  id: string;
  filename: string;
  size?: number;
  uploaded_at?: string;
}

interface Meeting {
  id: string;
  platform: string;
  meeting_link: string;
  status: string;
  created_at: string;
  started_at?: string;
  ended_at?: string;
  duration_minutes?: number;
}

export default function AgentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [promptExpanded, setPromptExpanded] = useState(false);
  const [meetingLink, setMeetingLink] = useState("");
  const [joiningMeeting, setJoiningMeeting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [stoppingMeetingId, setStoppingMeetingId] = useState<string | null>(null);

  const fetchAgent = useCallback(async () => {
    try {
      const { getAgent, getDocuments, getMeetings } = await import(
        "@/lib/api"
      );
      // TODO: Replace with actual API calls once backend is connected
      const [agentData, docsData, meetingsData] = await Promise.allSettled([
        getAgent(id),
        getDocuments(id),
        getMeetings(), // TODO: Add getMeetingsByAgent(id) when available
      ]);

      if (agentData.status === "fulfilled") {
        setAgent(agentData.value);
      }
      if (docsData.status === "fulfilled") {
        setDocuments(docsData.value);
      }
      if (meetingsData.status === "fulfilled") {
        // TODO: Filter meetings by agent_id on the client for now
        setMeetings(meetingsData.value);
      }
    } catch {
      // TODO: Handle error states with proper error boundary
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchAgent();
  }, [fetchAgent]);

  async function handleFileUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const { uploadDocument } = await import("@/lib/api");
      for (const file of Array.from(files)) {
        await uploadDocument(id, file);
      }
      // Refresh documents list
      const { getDocuments } = await import("@/lib/api");
      const docs = await getDocuments(id);
      setDocuments(docs);
    } catch {
      // TODO: Show upload error toast
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteDocument(docId: string) {
    try {
      const { deleteDocument, getDocuments } = await import("@/lib/api");
      await deleteDocument(docId);
      const docs = await getDocuments(id);
      setDocuments(docs);
    } catch {
      // TODO: Show delete error toast
    }
  }

  async function handleJoinMeeting() {
    if (!meetingLink.trim()) return;
    setJoiningMeeting(true);
    try {
      const { createMeeting } = await import("@/lib/api");

      await createMeeting({
        meeting_link: meetingLink,
        agent_id: id,
      });
      setMeetingLink("");
      // Refresh meetings
      const { getMeetings } = await import("@/lib/api");
      const meetingsData = await getMeetings();
      setMeetings(meetingsData);
    } catch {
      // TODO: Show join error toast
    } finally {
      setJoiningMeeting(false);
    }
  }

  async function handleStopMeeting(meetingId: string) {
    setStoppingMeetingId(meetingId);
    try {
      const { stopMeeting, getMeetings } = await import("@/lib/api");
      await stopMeeting(meetingId);
      const meetingsData = await getMeetings();
      setMeetings(meetingsData);
    } catch {
      // Meeting may already be stopped
    } finally {
      setStoppingMeetingId(null);
    }
  }

  async function handleDeleteAgent() {
    setDeleting(true);
    try {
      const { deleteAgent } = await import("@/lib/api");
      await deleteAgent(id);
      router.push("/dashboard/agents");
    } catch {
      // TODO: Show delete error toast
      setDeleting(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    handleFileUpload(e.dataTransfer.files);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5"
          nativeButton={false} render={<Link href="/dashboard/agents" />}
        >
          <ArrowLeft className="size-3.5" />
          Back to Agents
        </Button>
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border py-16">
          <Bot className="size-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Agent not found.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Navigation */}
      <Button
        variant="ghost"
        size="sm"
        className="gap-1.5"
        nativeButton={false} render={<Link href="/dashboard/agents" />}
      >
        <ArrowLeft className="size-3.5" />
        Back to Agents
      </Button>

      {/* Agent Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">{agent.name}</h1>
            <Badge variant={agent.mode === "custom" ? "default" : "secondary"}>
              {agent.mode === "custom" ? "Custom" : "General"}
            </Badge>
          </div>
          {agent.description && (
            <p className="text-sm text-muted-foreground">
              {agent.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5"
            nativeButton={false} render={<Link href={`/dashboard/agents/${id}/edit`} />}
          >
            <Edit className="size-3.5" />
            Edit
          </Button>
          <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogTrigger
              render={
                <Button variant="destructive" size="sm" className="gap-1.5" />
              }
            >
              <Trash2 className="size-3.5" />
              Delete
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete Agent</DialogTitle>
                <DialogDescription>
                  Are you sure you want to delete &ldquo;{agent.name}&rdquo;?
                  This action cannot be undone. All associated documents and
                  meeting history will be permanently removed.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setDeleteDialogOpen(false)}
                  disabled={deleting}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleDeleteAgent}
                  disabled={deleting}
                >
                  {deleting ? "Deleting..." : "Delete Agent"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* System Prompt */}
      {agent.system_prompt && (
        <Card>
          <CardHeader>
            <button
              type="button"
              onClick={() => setPromptExpanded(!promptExpanded)}
              className="flex w-full items-center justify-between"
            >
              <CardTitle>System Prompt</CardTitle>
              {promptExpanded ? (
                <ChevronUp className="size-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="size-4 text-muted-foreground" />
              )}
            </button>
          </CardHeader>
          {promptExpanded && (
            <CardContent>
              <pre className="whitespace-pre-wrap rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
                {agent.system_prompt}
              </pre>
            </CardContent>
          )}
        </Card>
      )}

      {/* Documents */}
      <Card>
        <CardHeader>
          <CardTitle>Documents</CardTitle>
          <CardDescription>
            Upload files to give this agent context for your meetings.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Upload Area */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed py-8 transition-colors ${
              dragOver
                ? "border-primary bg-primary/5"
                : "border-border hover:border-muted-foreground/25"
            }`}
          >
            <Upload className="size-5 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {uploading
                ? "Uploading..."
                : "Drag and drop files here, or click to browse"}
            </p>
            <label>
              <input
                type="file"
                className="hidden"
                multiple
                onChange={(e) => handleFileUpload(e.target.files)}
                disabled={uploading}
              />
              <Button
                variant="outline"
                size="sm"
                className="mt-1"
                disabled={uploading}
                onClick={(e) => {
                  const input = (e.currentTarget as HTMLElement)
                    .closest("label")
                    ?.querySelector("input");
                  input?.click();
                }}
              >
                {uploading ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Plus className="size-3.5" />
                )}
                Choose Files
              </Button>
            </label>
          </div>

          {/* Document List */}
          {documents.length > 0 && (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between rounded-lg border border-border p-3"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="size-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{doc.filename}</p>
                      {doc.uploaded_at && (
                        <p className="text-xs text-muted-foreground">
                          Uploaded {doc.uploaded_at}
                        </p>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleDeleteDocument(doc.id)}
                  >
                    <Trash2 className="size-3.5 text-muted-foreground" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {documents.length === 0 && (
            <p className="text-center text-xs text-muted-foreground">
              No documents uploaded yet.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Start Meeting */}
      <Card>
        <CardHeader>
          <CardTitle>Start a Meeting</CardTitle>
          <CardDescription>
            Have this agent join a live meeting to take notes and provide
            summaries.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="meeting-link">Meeting Link</Label>
            <div className="flex gap-2">
              <Input
                id="meeting-link"
                placeholder="https://meet.google.com/abc-defg-hij"
                value={meetingLink}
                onChange={(e) => setMeetingLink(e.target.value)}
              />
              <Button
                onClick={handleJoinMeeting}
                disabled={!meetingLink.trim() || joiningMeeting}
                className="shrink-0 gap-1.5"
              >
                {joiningMeeting ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Video className="size-3.5" data-icon="inline-start" />
                )}
                Join Meeting
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Paste a Zoom, Teams, or Google Meet link
            </p>
          </div>
        </CardContent>
      </Card>

      <Separator />

      {/* Meeting History */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">
          Meeting History
        </h2>
        {meetings.length > 0 ? (
          <div className="space-y-2">
            {meetings.map((meeting) => (
              <div
                key={meeting.id}
                className="flex items-center justify-between rounded-lg border border-border p-3"
              >
                <Link
                  href={`/dashboard/meetings/${meeting.id}`}
                  className="flex flex-col gap-1 flex-1 hover:opacity-80"
                >
                  <p className="text-sm font-medium">
                    {meeting.platform.charAt(0).toUpperCase() + meeting.platform.slice(1)} Meeting
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(meeting.created_at).toLocaleString()}
                  </p>
                </Link>
                <div className="flex items-center gap-3">
                  <Badge
                    variant={
                      meeting.status === "active"
                        ? "default"
                        : meeting.status === "ended"
                        ? "secondary"
                        : "outline"
                    }
                    className={meeting.status === "active" ? "bg-green-600" : ""}
                  >
                    {meeting.status === "active" ? "Live" : meeting.status}
                  </Badge>
                  {meeting.status === "active" && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleStopMeeting(meeting.id)}
                      disabled={stoppingMeetingId === meeting.id}
                    >
                      {stoppingMeetingId === meeting.id ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <>
                          <Square className="size-3 mr-1" />
                          Stop Bot
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border py-10">
            <Video className="size-5 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              No meetings yet with this agent.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
