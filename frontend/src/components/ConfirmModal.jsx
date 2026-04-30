import React from "react";
import { Button } from "./ui/button";
import { Trash2, AlertTriangle } from "lucide-react";

export default function ConfirmModal({ 
  isOpen, 
  title, 
  message, 
  onConfirm, 
  onCancel, 
  confirmText = "Delete",
  cancelText = "Cancel",
  variant = "destructive" 
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300 animate-in fade-in" 
        onClick={onCancel}
      />
      
      {/* Modal Content */}
      <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-border/50 bg-card p-6 shadow-2xl transition-all duration-300 animate-in zoom-in-95 slide-in-from-bottom-4">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className={`flex h-12 w-12 items-center justify-center rounded-full ${variant === 'destructive' ? 'bg-destructive/15 text-destructive' : 'bg-primary/15 text-primary'}`}>
            {variant === 'destructive' ? <Trash2 size={24} /> : <AlertTriangle size={24} />}
          </div>
          
          <div className="space-y-2">
            <h3 className="text-xl font-bold tracking-tight text-foreground">{title}</h3>
            <p className="text-sm text-muted-foreground">{message}</p>
          </div>
          
          <div className="mt-4 flex w-full gap-3">
            <Button 
              variant="outline" 
              className="flex-1 rounded-xl py-6" 
              onClick={onCancel}
            >
              {cancelText}
            </Button>
            <Button 
              variant={variant} 
              className="flex-1 rounded-xl py-6 font-bold shadow-lg shadow-destructive/20" 
              onClick={onConfirm}
            >
              {confirmText}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
