import { forwardRef } from 'react';

/**
 * Label en mayúsculas con tracking (idea estructural de survey_squeleton,
 * ver src/index.css .colmena-label) + input con la piel de Colmena.
 */
const FormField = forwardRef(function FormField({ label, error, hint, type = 'text', children, ...inputProps }, ref) {
  return (
    <label className="flex flex-col gap-2">
      <span className="colmena-label">{label}</span>
      {children || (
        <input
          ref={ref}
          type={type}
          className={`colmena-input h-11 px-4 text-sm text-dark placeholder:text-muted ${error ? 'has-error' : ''}`}
          {...inputProps}
        />
      )}
      {error ? (
        <span className="text-xs font-medium text-danger">{error}</span>
      ) : hint ? (
        <span className="text-xs text-muted">{hint}</span>
      ) : null}
    </label>
  );
});

export default FormField;
