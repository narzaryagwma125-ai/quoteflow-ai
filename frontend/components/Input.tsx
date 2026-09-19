import { forwardRef } from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
  prefix?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, prefix, id, className = "", ...rest }, ref) => {
    const inputId = id ?? `input-${label.replace(/\W+/g, "-").toLowerCase()}`;
    return (
      <div className="w-full">
        <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
          {label}
        </label>
        <div className="relative">
          {prefix && (
            <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-sm text-slate-500">
              {prefix}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            aria-invalid={error ? true : undefined}
            className={`w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 ${
              prefix ? "pl-7" : ""
            } ${
              error
                ? "border-red-400 focus:ring-red-200"
                : "border-slate-300 focus:border-brand-500 focus:ring-brand-200"
            } ${className}`}
            {...rest}
          />
        </div>
        {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
        {!error && hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      </div>
    );
  },
);

Input.displayName = "Input";