"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, ArrowRight, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { personaDescriptions, personaPresets, voiceOptions } from "@/lib/constants";

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [botName, setBotName] = useState("");
  const [selectedPreset, setSelectedPreset] = useState<string>(personaPresets[0]);
  const [customPersona, setCustomPersona] = useState("");
  const [isCustom, setIsCustom] = useState(false);
  const [voice, setVoice] = useState<"MALE" | "FEMALE">("FEMALE");
  const [saving, setSaving] = useState(false);

  async function handleComplete() {
    setSaving(true);
    try {
      await fetch("/api/bot-profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: botName,
          persona: isCustom ? customPersona : personaDescriptions[selectedPreset] ?? selectedPreset,
          voice,
          responseMode: "WAKE_WORD_ONLY"
        })
      });
      router.push("/dashboard");
    } catch {
      setSaving(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-xl space-y-8">
        <div className="flex flex-col items-center space-y-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-primary text-primary-foreground shadow-glow">
            <Sparkles className="h-8 w-8" />
          </div>
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">Meeting Bot</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">Set up your bot</h1>
            <p className="mt-2 text-sm text-muted-foreground">Step {step} of 3</p>
          </div>
        </div>

        <div className="flex gap-2">
          {[1, 2, 3].map((s) => (
            <div key={s} className={`h-1.5 flex-1 rounded-full transition-colors ${s <= step ? "bg-primary" : "bg-secondary"}`} />
          ))}
        </div>

        <Card>
          <CardContent className="p-8">
            {step === 1 && (
              <div className="space-y-6">
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold">Name your bot</h2>
                  <p className="text-sm text-muted-foreground">
                    This becomes the wake word. Say it in a meeting and your bot will respond.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="bot-name">Bot name</Label>
                  <Input
                    id="bot-name"
                    value={botName}
                    onChange={(e) => setBotName(e.target.value)}
                    placeholder="e.g. Nova, Sage, Atlas..."
                    autoFocus
                  />
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-6">
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold">Pick a persona</h2>
                  <p className="text-sm text-muted-foreground">Choose how your bot communicates in meetings.</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {personaPresets.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => {
                        setSelectedPreset(preset);
                        setIsCustom(false);
                      }}
                      className={`rounded-2xl border p-4 text-left text-sm font-medium transition hover:border-primary/50 ${
                        !isCustom && selectedPreset === preset
                          ? "border-primary bg-primary/10 text-foreground"
                          : "border-border text-muted-foreground"
                      }`}
                    >
                      {preset}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setIsCustom(true)}
                    className={`rounded-2xl border p-4 text-left text-sm font-medium transition hover:border-primary/50 ${
                      isCustom ? "border-primary bg-primary/10 text-foreground" : "border-border text-muted-foreground"
                    }`}
                  >
                    Other...
                  </button>
                </div>
                {isCustom && (
                  <Textarea
                    value={customPersona}
                    onChange={(e) => setCustomPersona(e.target.value)}
                    placeholder="Describe your bot's personality and communication style..."
                    autoFocus
                  />
                )}
              </div>
            )}

            {step === 3 && (
              <div className="space-y-6">
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold">Pick a voice</h2>
                  <p className="text-sm text-muted-foreground">Choose how your bot sounds when speaking in meetings.</p>
                </div>
                <RadioGroup
                  value={voice}
                  onValueChange={(v) => setVoice(v as "MALE" | "FEMALE")}
                  className="grid gap-4 sm:grid-cols-2"
                >
                  {voiceOptions.map((option) => (
                    <label
                      key={option.value}
                      className={`flex cursor-pointer items-center gap-3 rounded-2xl border p-5 transition hover:border-primary/50 ${
                        voice === option.value ? "border-primary bg-primary/10" : "border-border"
                      }`}
                    >
                      <RadioGroupItem value={option.value} />
                      <span className="font-medium">{option.label}</span>
                    </label>
                  ))}
                </RadioGroup>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex justify-between">
          <Button variant="outline" onClick={() => setStep(step - 1)} disabled={step === 1}>
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          {step < 3 ? (
            <Button
              onClick={() => setStep(step + 1)}
              disabled={step === 1 && botName.length < 2}
            >
              Next
              <ArrowRight className="h-4 w-4" />
            </Button>
          ) : (
            <Button onClick={handleComplete} disabled={saving}>
              {saving ? "Creating..." : "Complete Setup"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
