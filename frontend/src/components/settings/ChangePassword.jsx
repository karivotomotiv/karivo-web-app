import { useState } from "react";
import { api, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyRound } from "lucide-react";
import { toast } from "sonner";

export const ChangePassword = () => {
  const [cur, setCur] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    if (pw.length < 8) return toast.error("Yeni şifre en az 8 karakter olmalı");
    if (pw !== pw2) return toast.error("Yeni şifreler eşleşmiyor");
    setSaving(true);
    try {
      const { data } = await api.post("/auth/change-password", { current_password: cur, new_password: pw });
      localStorage.setItem("ks_token", data.token);
      toast.success("Şifreniz değiştirildi. Diğer cihazlardaki oturumlar kapatıldı.");
      setCur(""); setPw(""); setPw2("");
    } catch (err) { toast.error(extractError(err)); } finally { setSaving(false); }
  };

  return (
    <form onSubmit={save} className="space-y-3 rounded-xl border border-slate-200 p-4" data-testid="change-password-form">
      <div className="text-sm font-bold text-slate-900 flex items-center gap-2"><KeyRound className="w-4 h-4" /> Şifremi Değiştir</div>
      <div className="space-y-1.5"><Label className="text-xs">Mevcut Şifre</Label>
        <Input type="password" required value={cur} onChange={(e) => setCur(e.target.value)} autoComplete="current-password" data-testid="change-password-current" /></div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1.5"><Label className="text-xs">Yeni Şifre</Label>
          <Input type="password" required value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" data-testid="change-password-new" /></div>
        <div className="space-y-1.5"><Label className="text-xs">Yeni Şifre (Tekrar)</Label>
          <Input type="password" required value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" data-testid="change-password-new2" /></div>
      </div>
      <Button type="submit" size="sm" disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="change-password-save">{saving ? "Kaydediliyor..." : "Şifreyi Değiştir"}</Button>
    </form>
  );
};
