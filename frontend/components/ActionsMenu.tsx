"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";

export function ActionsMenu({
  busy,
  onDocx,
  onPdf,
  onDuplicate,
  onDelete,
}: {
  busy?: boolean;
  onDocx: () => void;
  onPdf: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const run = (fn: () => void) => {
    setOpen(false);
    fn();
  };

  return (
    <div className="relative" ref={rootRef}>
      <Button
        variant="ghost"
        size="sm"
        aria-label="Actions"
        title="More actions"
        disabled={busy}
        onClick={() => setOpen((o) => !o)}
      >
        &#8943;
      </Button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 w-40 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          <MenuButton onClick={() => run(onDocx)}>DOCX</MenuButton>
          <MenuButton onClick={() => run(onPdf)}>PDF</MenuButton>
          <MenuButton onClick={() => run(onDuplicate)}>Duplicate</MenuButton>
          <MenuButton danger onClick={() => run(onDelete)}>
            Delete
          </MenuButton>
        </div>
      )}
    </div>
  );
}

function MenuButton({
  children,
  onClick,
  danger,
}: {
  children: React.ReactNode;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center px-3 py-2 text-left text-sm ${
        danger ? "text-red-600 hover:bg-red-50" : "text-slate-700 hover:bg-slate-50"
      }`}
    >
      {children}
    </button>
  );
}