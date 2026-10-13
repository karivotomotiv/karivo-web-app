import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogFooter,
  AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel,
} from "@/components/ui/alert-dialog";

export const ConfirmDeleteDialog = ({ confirm, onClose, onConfirm }) => (
  <AlertDialog open={!!confirm} onOpenChange={(o) => !o && onClose()}>
    <AlertDialogContent data-testid="log-confirm-dialog">
      <AlertDialogHeader>
        <AlertDialogTitle>{confirm?.title}</AlertDialogTitle>
        <AlertDialogDescription>{confirm?.desc}</AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel data-testid="log-confirm-cancel">Vazgeç</AlertDialogCancel>
        <AlertDialogAction className="bg-rose-600 hover:bg-rose-700" onClick={onConfirm} data-testid="log-confirm-delete">
          Evet, Sil
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);
