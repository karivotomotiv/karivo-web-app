import { useEffect, useState } from "react";
import { api, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Mail, Save, Info } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { ChangePassword } from "@/components/settings/ChangePassword";
import { UserManagement } from "@/components/settings/UserManagement";
import { Devices } from "@/components/settings/Devices";

export default function SettingsDialog({ open, onOpenChange }) {
  const [settings, setSettings] = useState(null);
  const [email, setEmail] = useState("");
  const [recipients, setRecipients] = useState([]);
  const [saving, setSaving] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const [s, r] = await Promise.all([api.get("/auth/settings"), api.get("/auth/recipients")]);
        setSettings(s.data);
        setEmail(s.data.notification_email || "");
        setRecipients(r.data);
      } catch (e) {
        toast.error(extractError(e));
      }
    })();
  }, [open]);

  const save = async (e) => {
    e?.preventDefault();
    setSaving(true);
    try {
      await api.put("/auth/settings", { notification_email: email.trim() || null });
      toast.success("Ayarlar kaydedildi");
      // Reload recipient preview
      const r = await api.get("/auth/recipients");
      setRecipients(r.data);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Ayarlar</DialogTitle>
          <DialogDescription>
            Düşük stok uyarıları için gerçek bir e-posta adresi girin. Boş bırakırsanız giriş e-postanız kullanılır.
          </DialogDescription>
        </DialogHeader>

        {user?.role === "admin" && open && <UserManagement meId={user.id} />}
        {open && <ChangePassword />}
        {open && <Devices />}

        <div className="text-sm font-bold text-slate-900 pt-2">Bildirim Ayarları</div>
        <Alert className="border-sky-300 bg-sky-50">
          <Info className="h-4 w-4 text-sky-700" />
          <AlertDescription className="text-sky-900 text-xs">
            E-posta sağlayıcısı test/sahte adreslere (örn. @sirket.com) teslimat yapmaz. Lütfen gerçekten erişebildiğiniz bir e-posta adresi girin.
          </AlertDescription>
        </Alert>

        <form onSubmit={save} className="space-y-4 pt-2">
          <div className="space-y-2">
            <Label>Giriş kullanıcısı</Label>
            <div className="text-sm text-slate-700" data-testid="settings-user">
              {settings?.name} · <span className="text-slate-500">{settings?.email}</span>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="notif">Bildirim E-postası</Label>
            <Input
              id="notif"
              type="email"
              placeholder="ornek@gmail.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              data-testid="settings-notification-email"
            />
          </div>

          {recipients.length > 0 && (
            <div className="pt-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Düşük stok e-postaları buraya gönderilir
              </Label>
              <ul className="mt-2 space-y-1" data-testid="settings-recipients">
                {recipients.map((r) => (
                  <li key={r.login_email} className="flex items-center justify-between text-sm bg-slate-50 rounded-lg px-3 py-2 border border-slate-200">
                    <span className="text-slate-700 font-medium">{r.name}</span>
                    <span className="inline-flex items-center gap-2 text-slate-900 font-mono text-xs">
                      <Mail className="w-3 h-3" />
                      {r.effective}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Kapat</Button>
            <Button type="submit" disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="settings-save">
              <Save className="w-4 h-4 mr-2" />
              {saving ? "Kaydediliyor..." : "Kaydet"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
