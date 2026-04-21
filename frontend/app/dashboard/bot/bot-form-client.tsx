"use client";

import { useState, useEffect, useRef, type ChangeEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FileText, Save, Trash2, Upload } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { useBotProfile } from "@/hooks/use-bot-profile";
import { personaDescriptions, personaPresets, responseModeOptions, voiceOptions } from "@/lib/constants";
import type { BotProfileDTO, ResponseMode, VoiceOption } from "@/types";

export function BotFormClient({ initialBot }: { initialBot: BotProfileDTO }) {
  const { data: bot = initialBot, updateBotProfile, isSaving } = useBotProfile({ initialData: initialBot });
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const initializedRef = useRef(false);
  const [name, setName] = useState(initialBot.name);
  const [persona, setPersona] = useState(initialBot.persona);
  const [voice, setVoice] = useState<VoiceOption>(initialBot.voice);
  const [responseMode, setResponseMode] = useState<ResponseMode>(initialBot.responseMode);
  const [saved, setSaved] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    if (bot && !initializedRef.current) {
      setName(bot.name);
      setPersona(bot.persona);
      setVoice(bot.voice);
      setResponseMode(bot.responseMode);
      initializedRef.current = true;
    }
  }, [bot]);

  async function handleSave() {
    await updateBotProfile({ name, persona, voice, responseMode });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setUploadError(null);
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { error?: string };
        throw new Error(body.error ?? "Upload failed");
      }

      await queryClient.invalidateQueries({ queryKey: ["bot-profile"] });
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Configuration"
        title="My Bot"
        description="Customize your AI meeting copilot."
        actions={
          <Button onClick={handleSave} disabled={isSaving || name.length < 2}>
            <Save className="h-4 w-4" />
            {saved ? "Saved!" : isSaving ? "Saving..." : "Save changes"}
          </Button>
        }
      />

      <div className="grid gap-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Identity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="bot-name">Bot name (wake word)</Label>
              <Input id="bot-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Nova" />
            </div>
            <Separator />
            <div className="space-y-3">
              <Label>Voice</Label>
              <RadioGroup value={voice} onValueChange={(value) => setVoice(value as VoiceOption)} className="flex gap-4">
                {voiceOptions.map((option) => (
                  <label
                    key={option.value}
                    className={`flex cursor-pointer items-center gap-2 rounded-xl border px-4 py-3 transition ${
                      voice === option.value ? "border-primary bg-primary/10" : "border-border"
                    }`}
                  >
                    <RadioGroupItem value={option.value} aria-label={option.label} />
                    <span className="text-sm font-medium">{option.label}</span>
                  </label>
                ))}
              </RadioGroup>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Response Mode</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {responseModeOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setResponseMode(option.value as ResponseMode)}
                className={`w-full rounded-2xl border p-5 text-left transition ${
                  responseMode === option.value ? "border-primary bg-primary/10" : "border-border"
                }`}
              >
                <p className="font-medium">{option.label}</p>
                <p className="mt-1 text-sm text-muted-foreground">{option.description}</p>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Persona</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              placeholder="Describe how your bot should communicate..."
              rows={4}
            />
            <div className="flex flex-wrap gap-2">
              {personaPresets.map((preset) => (
                <Button
                  key={preset}
                  variant="outline"
                  size="sm"
                  onClick={() => setPersona(personaDescriptions[preset] ?? preset)}
                >
                  {preset}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Global Documents</CardTitle>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={handleFileChange}
              />
              <Button
                variant="outline"
                size="sm"
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                <Upload className="h-4 w-4" />
                {uploading ? "Uploading..." : "Upload"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {uploadError ? <p className="mb-4 text-sm text-destructive">{uploadError}</p> : null}
            {bot.documents.length > 0 ? (
              <div className="space-y-3">
                {bot.documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between rounded-xl border border-border p-4">
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium">{doc.name}</p>
                        <p className="text-xs text-muted-foreground">{(doc.fileSize / 1024).toFixed(0)} KB</p>
                      </div>
                    </div>
                    <Button variant="ghost" size="icon">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-border p-8 text-center">
                <p className="text-sm text-muted-foreground">
                  No documents uploaded. Upload PDFs or Word files to give your bot context in every meeting.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
