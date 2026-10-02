import { forwardRef } from "react";

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, hint, id, className = "", rows = 4, ...rest }, ref) => {
    const inputId = id ?? `textarea-${label.replace(/\W+/g, "-").toLowerCase()}`;
    return (
      <div className="w-full">
        <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
          {label}
        </label>
        <textarea
          ref={ref}
          id={inputId}
          rows={rows}
          aria-invalid={error ? true : undefined}
          className={`w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 ${
            error
              ? "border-red-400 focus:ring-red-200"
              : "border-slate-300 focus:border-brand-500 focus:ring-brand-200"
          } ${className}`}
          {...rest}
        />
        {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
        {!error && hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      </div>
    );
  },
);

Textarea.displayName = "Textarea";