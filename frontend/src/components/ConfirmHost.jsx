import { useEffect, useState } from "react";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogFooter,
  AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel,
} from "@/components/ui/alert-dialog";

let show = null;

export const askConfirm = (message, { title = "Emin misiniz?", confirmText = "Evet, Devam Et" } = {}) =>
  new Promise((resolve) => (show ? show({ message, title, confirmText, resolve }) : resolve(false)));

export const ConfirmHost = () => {
  const [req, setReq] = useState(null);
  useEffect(() => { show = setReq; return () => { show = null; }; }, []);

  const close = (ok) => { req?.resolve(ok); setReq(null); };

  return (
    <AlertDialog open={!!req} onOpenChange={(o) => !o && close(false)}>
      <AlertDialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-lg rounded-xl" data-testid="confirm-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>{req?.title}</AlertDialogTitle>
          <AlertDialogDescription className="whitespace-pre-line text-left" data-testid="confirm-dialog-message">{req?.message}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="gap-2">
          <AlertDialogCancel onClick={() => close(false)} data-testid="confirm-dialog-cancel">Vazgeç</AlertDialogCancel>
          <AlertDialogAction className="bg-rose-600 hover:bg-rose-700" onClick={() => close(true)} data-testid="confirm-dialog-ok">
            {req?.confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
