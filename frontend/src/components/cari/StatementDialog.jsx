import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { FileDown, Loader2 } from "lucide-react";
import { toast } from "sonner";

export const StatementDialog = ({ cariId, cariName }) => {
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [busy, setBusy] = useState(false);

  const download = async () => {
    setBusy(true);
    try {
      const params = {};
      if (start) params.start = start;
      if (end) params.end = end;
      const { data } = await api.get(`/cariler/${cariId}/statement`, { params, responseType: "blob" });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ekstre-${cariName}-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setOpen(false);
    } catch {
      toast.error("Ekstre oluşturulamadı. Tarihleri kontrol edin.");
    }
    setBusy(false);
  };

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)} data-testid="cari-statement-btn">
        <FileDown className="w-4 h-4 mr-2" /> Ekstre (PDF)
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="cari-statement-dialog">
          <DialogHeader>
            <DialogTitle>Cari Ekstresi — {cariName}</DialogTitle>
            <DialogDescription>Tarih seçmezseniz tüm hareketler eklenir. Başlangıç seçilirse önceki bakiye "Devreden" olarak en üstte görünür.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Başlangıç</Label>
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} data-testid="cari-statement-start" />
            </div>
            <div className="space-y-2">
              <Label>Bitiş</Label>
              <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} data-testid="cari-statement-end" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} data-testid="cari-statement-cancel">Vazgeç</Button>
            <Button onClick={download} disabled={busy} data-testid="cari-statement-download">
              {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FileDown className="w-4 h-4 mr-2" />} PDF İndir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};
