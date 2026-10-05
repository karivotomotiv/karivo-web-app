import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Navigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Building2, Lock } from "lucide-react";

const DEMO_USERS = [
  { name: "Ahmet (Kullanıcı 1)", email: "ahmet@sirket.com", password: "Ahmet2026!" },
  { name: "Ayşe (Kullanıcı 2)", email: "ayse@sirket.com", password: "Ayse2026!" },
];

export default function Login() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e?.preventDefault();
    setErr("");
    setLoading(true);
    const r = await login(email, password);
    setLoading(false);
    if (!r.ok) setErr(r.error);
  };

  const quickLogin = async (u) => {
    setEmail(u.email);
    setPassword(u.password);
    setErr("");
    setLoading(true);
    const r = await login(u.email, u.password);
    setLoading(false);
    if (!r.ok) setErr(r.error);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(13,148,136,0.08),transparent_50%),radial-gradient(circle_at_80%_80%,rgba(15,23,42,0.06),transparent_50%)]" />
      <Card className="w-full max-w-md relative shadow-xl border-slate-200">
        <CardHeader className="space-y-3 text-center pb-4">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-slate-900 text-white flex items-center justify-center shadow-md">
            <Building2 className="w-7 h-7" />
          </div>
          <CardTitle className="text-2xl font-extrabold tracking-tight text-slate-900">
            Şirket Yönetim
          </CardTitle>
          <CardDescription className="text-slate-600">
            Gelir, gider, stok ve görev takibi için hesabınıza giriş yapın.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                E-posta
              </Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ahmet@sirket.com"
                autoComplete="email"
                required
                data-testid="login-email-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Şifre
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
                data-testid="login-password-input"
              />
            </div>
            {err && (
              <Alert variant="destructive" data-testid="login-error">
                <AlertDescription>{err}</AlertDescription>
              </Alert>
            )}
            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-slate-900 hover:bg-slate-800 text-white"
              data-testid="login-submit-btn"
            >
              <Lock className="w-4 h-4 mr-2" />
              {loading ? "Giriş yapılıyor..." : "Giriş Yap"}
            </Button>
          </form>

          <div className="relative py-2">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-slate-500">Hızlı Giriş</span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2">
            {DEMO_USERS.map((u, i) => (
              <Button
                key={u.email}
                type="button"
                variant="outline"
                onClick={() => quickLogin(u)}
                disabled={loading}
                className="justify-start border-slate-200 hover:border-teal-500 hover:bg-teal-50 hover:text-teal-900"
                data-testid={`quick-login-user${i + 1}`}
              >
                <span className="w-8 h-8 rounded-lg bg-teal-100 text-teal-700 flex items-center justify-center text-sm font-bold mr-3">
                  {u.name.charAt(0)}
                </span>
                <div className="flex flex-col items-start">
                  <span className="text-sm font-semibold">{u.name}</span>
                  <span className="text-xs text-slate-500">{u.email}</span>
                </div>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
