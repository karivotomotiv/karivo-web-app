import { useState } from "react";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogFooter,
  AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { FileSpreadsheet, Loader2 } from "lucide-react";

export const ConfirmDeleteDialog = ({ confirm, onClose, onConfirm, onExport }) => {
  const [busy, setBusy] = useState(false);
  const exportFirst = async () => { setBusy(true); await onExport(); setBusy(false); };

  return (
    <AlertDialog open={!!confirm} onOpenChange={(o) => !o && onClose()}>
      <AlertDialogContent data-testid="log-confirm-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>{confirm?.title}</AlertDialogTitle>
          <AlertDialogDescription>{confirm?.desc}</AlertDialogDescription>
        </AlertDialogHeader>
        <Button variant="outline" onClick={exportFirst} disabled={busy} className="justify-start" data-testid="log-confirm-export">
          {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FileSpreadsheet className="w-4 h-4 mr-2 text-emerald-600" />}
          Önce Excel olarak indir
        </Button>
        <AlertDialogFooter>
          <AlertDialogCancel data-testid="log-confirm-cancel">Vazgeç</AlertDialogCancel>
          <AlertDialogAction className="bg-rose-600 hover:bg-rose-700" onClick={onConfirm} data-testid="log-confirm-delete">
            Evet, Sil
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
