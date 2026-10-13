import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { KeyRound, Mail, ShieldCheck, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

const STEPS = {
  email: { title: "Şifremi Unuttum", desc: "Sistemde kayıtlı e-posta adresinizi girin, size bir sıfırlama kodu gönderelim.", Icon: Mail },
  code: { title: "Kodu Girin", desc: "E-postanıza gelen 6 haneli kodu girin.", Icon: ShieldCheck },
  password: { title: "Yeni Şifre", desc: "Yeni şifrenizi belirleyin (en az 8 karakter).", Icon: KeyRound },
};

export default function SifremiUnuttum() {
  const navigate = useNavigate();
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  const run = async (fn) => {
    setErr(""); setLoading(true);
    try { await fn(); } catch (e) { setErr(extractError(e)); } finally { setLoading(false); }
  };
  const sendCode = (e) => {
    e?.preventDefault();
    run(async () => {
      const { data } = await api.post("/auth/forgot-password", { email: email.trim() });
      setInfo(`Kod ${data.sent_to} adresine gönderildi.`);
      setStep("code");
    });
  };
  const checkCode = (e) => {
    e.preventDefault();
    run(async () => { await api.post("/auth/verify-reset-code", { email: email.trim(), code: code.trim() }); setStep("password"); });
  };
  const resetPw = (e) => {
    e.preventDefault();
    if (pw.length < 8) { setErr("Şifre en az 8 karakter olmalı"); return; }
    if (pw !== pw2) { setErr("Şifreler eşleşmiyor"); return; }
    run(async () => {
      await api.post("/auth/reset-password", { email: email.trim(), code: code.trim(), new_password: pw });
      toast.success("Şifreniz güncellendi. Yeni şifrenizle giriş yapabilirsiniz.");
      navigate("/login");
    });
  };

  const { title, desc, Icon } = STEPS[step];
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-md shadow-xl border-slate-200" data-testid="forgot-card">
        <CardHeader className="space-y-3 text-center pb-4">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-slate-900 text-white flex items-center justify-center shadow-md"><Icon className="w-7 h-7" /></div>
          <CardTitle className="text-2xl font-extrabold tracking-tight text-slate-900" data-testid="forgot-step-title">{title}</CardTitle>
          <CardDescription className="text-slate-600">{desc}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {info && step !== "email" && <div className="text-xs text-teal-700 bg-teal-50 rounded-lg px-3 py-2" data-testid="forgot-info">{info}</div>}
          {step === "email" && (
            <form onSubmit={sendCode} className="space-y-4">
              <div className="space-y-2"><Label>E-posta</Label>
                <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ornek@gmail.com" data-testid="forgot-email-input" /></div>
              <Button type="submit" disabled={loading} className="w-full bg-slate-900 hover:bg-slate-800" data-testid="forgot-send-code-btn">{loading ? "Gönderiliyor..." : "Kod Gönder"}</Button>
            </form>
          )}
          {step === "code" && (
            <form onSubmit={checkCode} className="space-y-4">
              <div className="space-y-2"><Label>Doğrulama Kodu</Label>
                <Input inputMode="numeric" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="123456" className="text-center text-xl tracking-[0.5em] font-bold" data-testid="forgot-code-input" /></div>
              <Button type="submit" disabled={loading || code.length !== 6} className="w-full bg-slate-900 hover:bg-slate-800" data-testid="forgot-verify-code-btn">{loading ? "Kontrol ediliyor..." : "Kodu Doğrula"}</Button>
              <button type="button" onClick={sendCode} disabled={loading} className="w-full text-xs text-slate-500 hover:text-slate-900" data-testid="forgot-resend-btn">Kod gelmedi mi? Tekrar gönder</button>
            </form>
          )}
          {step === "password" && (
            <form onSubmit={resetPw} className="space-y-4">
              <div className="space-y-2"><Label>Yeni Şifre</Label>
                <Input type="password" required value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" data-testid="forgot-new-password" /></div>
              <div className="space-y-2"><Label>Yeni Şifre (Tekrar)</Label>
                <Input type="password" required value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" data-testid="forgot-new-password2" /></div>
              <Button type="submit" disabled={loading} className="w-full bg-slate-900 hover:bg-slate-800" data-testid="forgot-reset-btn">{loading ? "Kaydediliyor..." : "Şifreyi Güncelle"}</Button>
            </form>
          )}
          {err && <Alert variant="destructive" data-testid="forgot-error"><AlertDescription>{err}</AlertDescription></Alert>}
          <Link to="/login" className="flex items-center justify-center gap-1 text-sm text-slate-500 hover:text-slate-900" data-testid="forgot-back-login"><ArrowLeft className="w-4 h-4" /> Girişe dön</Link>
        </CardContent>
      </Card>
    </div>
  );
}
