import { useEffect, useState } from "react";
import { api, extractError, formatDateTime } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Users, Pencil, X, LogOut } from "lucide-react";
import { toast } from "sonner";

const UserRow = ({ u, meId, onSaved }) => {
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState({ name: u.name, email: u.email, password: "" });
  const [saving, setSaving] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    if (form.password && form.password.length < 8) return toast.error("Şifre en az 8 karakter olmalı");
    setSaving(true);
    try {
      const { data } = await api.put(`/admin/users/${u.id}`, { name: form.name.trim(), email: form.email.trim(), password: form.password || null });
      if (data.token) localStorage.setItem("ks_token", data.token);
      toast.success(`${data.user.name} güncellendi${form.password ? "; açık oturumları kapatıldı" : ""}`);
      setEdit(false); onSaved();
    } catch (err) { toast.error(extractError(err)); } finally { setSaving(false); }
  };

  const forceLogout = async () => {
    if (!window.confirm(`${u.name} kullanıcısının tüm cihazlardaki oturumları şimdi kapatılsın mı?`)) return;
    try { await api.post(`/admin/users/${u.id}/logout`); toast.success(`${u.name} sistemden çıkarıldı`); onSaved(); }
    catch (err) { toast.error(extractError(err)); }
  };
  const activeMin = u.last_active_at ? Math.round((Date.now() - new Date(u.last_active_at).getTime()) / 60000) : null;

  if (!edit) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2" data-testid={`admin-user-${u.id}`}>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">{u.name} {u.id === meId && <span className="text-xs text-slate-400">(siz)</span>} {u.role === "admin" && <Badge variant="outline" className="ml-1 text-[10px]">Yönetici</Badge>}</div>
          <div className="text-xs text-slate-500 truncate">{u.email}</div>
          <div className="text-[11px] text-slate-500" data-testid={`admin-user-activity-${u.id}`}>
            {activeMin !== null && activeMin <= 5 ? <span className="text-emerald-700 font-semibold">● Şu an aktif</span>
              : u.last_active_at ? `Son aktif: ${formatDateTime(u.last_active_at)}` : "Henüz aktiflik yok"}
            {u.last_device && ` · ${u.last_device.browser} · ${u.last_device.os}`} · {u.device_count} cihaz
          </div>
        </div>
        {u.id !== meId && (
          <Button size="sm" variant="ghost" className="text-rose-600 hover:bg-rose-50" onClick={forceLogout} title="Oturumlarını kapat" data-testid={`admin-user-logout-${u.id}`}><LogOut className="w-4 h-4" /></Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => { setForm({ name: u.name, email: u.email, password: "" }); setEdit(true); }} data-testid={`admin-user-edit-${u.id}`}><Pencil className="w-4 h-4" /></Button>
      </div>
    );
  }
  return (
    <form onSubmit={save} className="space-y-2 rounded-lg border border-slate-200 p-3" data-testid={`admin-user-form-${u.id}`}>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1"><Label className="text-xs">Ad</Label><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="admin-user-name" /></div>
        <div className="space-y-1"><Label className="text-xs">E-posta</Label><Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="admin-user-email" /></div>
      </div>
      <div className="space-y-1"><Label className="text-xs">Yeni Şifre (değişmeyecekse boş bırakın)</Label>
        <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" data-testid="admin-user-password" /></div>
      <div className="flex gap-2 justify-end">
        <Button type="button" size="sm" variant="outline" onClick={() => setEdit(false)} data-testid="admin-user-cancel"><X className="w-4 h-4" /></Button>
        <Button type="submit" size="sm" disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="admin-user-save">{saving ? "Kaydediliyor..." : "Kaydet"}</Button>
      </div>
    </form>
  );
};

export const UserManagement = ({ meId }) => {
  const [users, setUsers] = useState([]);
  const load = () => api.get("/admin/users").then(({ data }) => setUsers(data)).catch((e) => toast.error(extractError(e)));
  useEffect(() => { load(); }, []);
  return (
    <div className="space-y-2 rounded-xl border border-slate-200 p-4" data-testid="user-management">
      <div className="text-sm font-bold text-slate-900 flex items-center gap-2"><Users className="w-4 h-4" /> Kullanıcı Yönetimi</div>
      <p className="text-[11px] text-slate-500">Ad, e-posta veya şifre değiştirilebilir. Şifre/e-posta değişince kullanıcının açık oturumları kapanır.</p>
      {users.map((u) => <UserRow key={u.id} u={u} meId={meId} onSaved={load} />)}
    </div>
  );
};
