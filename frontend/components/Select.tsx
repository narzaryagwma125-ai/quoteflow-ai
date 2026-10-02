import { forwardRef } from "react";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  error?: string;
  children: React.ReactNode;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, id, className = "", children, ...rest }, ref) => {
    const inputId = id ?? `select-${label.replace(/\W+/g, "-").toLowerCase()}`;
    return (
      <div className="w-full">
        <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
          {label}
        </label>
        <select
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          className={`w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 ${
            error
              ? "border-red-400 focus:ring-red-200"
              : "border-slate-300 focus:border-brand-500 focus:ring-brand-200"
          } ${className}`}
          {...rest}
        >
          {children}
        </select>
        {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
      </div>
    );
  },
);

Select.displayName = "Select";