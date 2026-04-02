import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account and preferences.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>
            Your personal account information.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input id="name" defaultValue="Yash Goel" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" defaultValue="yash@synth.dev" />
          </div>
          <Button size="sm">Save Changes</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Credits</CardTitle>
          <CardDescription>
            Your usage balance and billing.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-baseline justify-between">
            <div>
              <p className="text-3xl font-bold">120</p>
              <p className="text-sm text-muted-foreground">credits remaining</p>
            </div>
            <Button variant="outline" size="sm">
              Buy More
            </Button>
          </div>
          <Separator />
          <div className="space-y-2 text-sm text-muted-foreground">
            <div className="flex justify-between">
              <span>Cost per meeting</span>
              <span>~3 credits</span>
            </div>
            <div className="flex justify-between">
              <span>Estimated meetings left</span>
              <span>~40</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Integrations</CardTitle>
          <CardDescription>
            Connect your meeting platforms.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <div>
              <p className="text-sm font-medium">Google Meet</p>
              <p className="text-xs text-muted-foreground">Not connected</p>
            </div>
            <Button variant="outline" size="sm">
              Connect
            </Button>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <div>
              <p className="text-sm font-medium">Zoom</p>
              <p className="text-xs text-muted-foreground">Not connected</p>
            </div>
            <Button variant="outline" size="sm">
              Connect
            </Button>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <div>
              <p className="text-sm font-medium">Microsoft Teams</p>
              <p className="text-xs text-muted-foreground">Not connected</p>
            </div>
            <Button variant="outline" size="sm">
              Connect
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
