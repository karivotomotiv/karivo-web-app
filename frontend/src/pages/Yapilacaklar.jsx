import { useEffect, useState } from "react";
import { api, formatDateTime, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, Trash2, ListChecks, Pencil } from "lucide-react";
import { toast } from "sonner";
import { askConfirm } from "@/components/ConfirmHost";

export default function Yapilacaklar() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ title: "", note: "" });

  const load = async () => {
    try { const { data } = await api.get("/todos"); setItems(data); }
    catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({ title: "", note: "" }); setOpen(true); };
  const openEdit = (it) => { setEditing(it); setForm({ title: it.title, note: it.note || "" }); setOpen(true); };

  const save = async (e) => {
    e?.preventDefault();
    if (!form.title.trim()) { toast.error("Görev adı gereklidir"); return; }
    try {
      if (editing) {
        await api.put(`/todos/${editing.id}`, { title: form.title, note: form.note });
        toast.success("Görev güncellendi");
      } else {
        await api.post("/todos", { title: form.title, note: form.note });
        toast.success("Görev eklendi");
      }
      setOpen(false);
      load();
    } catch (e) {
      toast.error(extractError(e));
    }
  };

  const toggle = async (it) => {
    try {
      await api.put(`/todos/${it.id}`, { completed: !it.completed });
      load();
    } catch (e) { toast.error(extractError(e)); }
  };

  const remove = async (id) => {
    if (!(await askConfirm("Bu görevi silmek istiyor musunuz?"))) return;
    try { await api.delete(`/todos/${id}`); toast.success("Silindi"); load(); }
    catch (e) { toast.error(extractError(e)); }
  };

  const open_count = items.filter((i) => !i.completed).length;
  const done_count = items.length - open_count;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-teal-100 text-teal-700 flex items-center justify-center">
            <ListChecks className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Yapılacaklar</h2>
            <p className="text-sm text-slate-600 mt-1">
              <span data-testid="todos-open-count">{open_count}</span> açık · <span data-testid="todos-done-count">{done_count}</span> tamamlandı
            </p>
          </div>
        </div>
        <Button onClick={openNew} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="todo-add-btn">
          <Plus className="w-4 h-4 mr-2" /> Yeni Görev
        </Button>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0 divide-y divide-slate-100">
          {items.length === 0 && (
            <div className="text-center text-slate-500 py-12">Henüz görev yok.</div>
          )}
          {items.map((it) => (
            <div key={it.id} className="p-4 flex items-start gap-4 hover:bg-slate-50" data-testid={`todo-item-${it.id}`}>
              <Checkbox
                checked={it.completed}
                onCheckedChange={() => toggle(it)}
                className="mt-1"
                data-testid={`todo-check-${it.id}`}
              />
              <div className="flex-1 min-w-0">
                <div className={`font-medium ${it.completed ? "line-through text-slate-400" : "text-slate-900"}`}>{it.title}</div>
                {it.note && <div className="text-sm text-slate-600 mt-1 whitespace-pre-wrap">{it.note}</div>}
                <div className="text-xs text-slate-500 mt-2 flex gap-3 flex-wrap">
                  <span>Ekleyen: <strong>{it.created_by_name}</strong></span>
                  <span>Eklenme: {formatDateTime(it.created_at)}</span>
                  {it.completed_at && <span className="text-emerald-700">Tamamlandı: {formatDateTime(it.completed_at)}</span>}
                </div>
              </div>
              <div className="inline-flex gap-1">
                <Button variant="ghost" size="sm" onClick={() => openEdit(it)} data-testid={`todo-edit-${it.id}`}>
                  <Pencil className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => remove(it.id)} className="text-rose-600 hover:bg-rose-50" data-testid={`todo-delete-${it.id}`}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Görevi Düzenle" : "Yeni Görev"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-2">
              <Label>Görev Adı</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="todo-form-title" />
            </div>
            <div className="space-y-2">
              <Label>Not</Label>
              <Textarea rows={4} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} data-testid="todo-form-note" />
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>İptal</Button>
              <Button type="submit" className="bg-slate-900 hover:bg-slate-800" data-testid="todo-form-save">Kaydet</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
