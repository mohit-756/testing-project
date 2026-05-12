import React, { forwardRef, useId } from 'react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { cn } from '../utils/utils';

const FormInput = forwardRef((
  {
    label,
    error,
    touched,
    isValid,
    type = 'text',
    placeholder,
    className,
    helpText,
    icon: Icon,
    required = false,
    disabled = false,
    ...props
  },
  ref
) => {
  const id = useId();
  const errorId = useId();
  const helpId = useId();

  const hasError = error && touched;
  const showValid = isValid && touched && !error;

  return (
    <div className="space-y-2">
      {label && (
        <label
          htmlFor={id}
          className="text-sm font-medium text-slate-700 dark:text-slate-300 block"
        >
          {label}
          {required && <span className="required-indicator" aria-hidden="true">*</span>}
          {required && <span className="sr-only">(required)</span>}
        </label>
      )}

      <div className="relative group">
        {Icon && (
          <Icon
            className={cn(
              'absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 transition-colors pointer-events-none',
              hasError ? 'text-red-400' : showValid ? 'text-emerald-500' : 'text-slate-400 group-focus-within:text-blue-500'
            )}
            aria-hidden="true"
          />
        )}

        <input
          ref={ref}
          id={id}
          type={type}
          placeholder={placeholder}
          disabled={disabled}
          aria-invalid={hasError ? 'true' : 'false'}
          aria-describedby={cn(hasError && errorId, helpText && helpId)}
          className={cn(
            'form-input interactive-element w-full transition-all',
            Icon && 'pl-12',
            hasError && 'border-red-300 bg-red-50 dark:bg-red-900/10 dark:border-red-700',
            showValid && 'border-emerald-300 bg-emerald-50 dark:bg-emerald-900/10 dark:border-emerald-700',
            disabled && 'opacity-50 cursor-not-allowed bg-slate-100 dark:bg-slate-800',
            className
          )}
          {...props}
        />

        {showValid && (
          <CheckCircle2
            className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-emerald-500 pointer-events-none"
            aria-hidden="true"
          />
        )}

        {hasError && (
          <AlertCircle
            className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-red-500 pointer-events-none"
            aria-hidden="true"
          />
        )}
      </div>

      {hasError && (
        <p
          id={errorId}
          role="alert"
          className="text-sm text-red-600 dark:text-red-400 flex items-start gap-2"
        >
          <span className="flex-shrink-0 mt-0.5" aria-hidden="true">•</span>
          <span>{error}</span>
        </p>
      )}

      {helpText && !hasError && (
        <p
          id={helpId}
          className="text-xs text-slate-500 dark:text-slate-400"
        >
          {helpText}
        </p>
      )}
    </div>
  );
});

FormInput.displayName = 'FormInput';

export default FormInput;
