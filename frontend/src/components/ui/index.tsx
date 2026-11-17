// Small shadcn-style primitives built on Tailwind.
import clsx from 'clsx'
import { useEffect, useId, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { num, parseNum } from '../../utils/format'

export function Button({ variant = 'primary', className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' }) {
  return (
    <button
      {...props}
      className={clsx(
        'inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
        variant === 'primary' && 'bg-accent text-accent-ink hover:brightness-110',
        variant === 'secondary' && 'border border-border bg-panel text-ink hover:bg-surface',
        variant === 'ghost' && 'text-ink hover:bg-surface',
        className,
      )}
    />
  )
}

export function Card({ title, children, className, actions }: { title?: ReactNode; children: ReactNode; className?: string; actions?: ReactNode }) {
  return (
    <section className={clsx('rounded-lg border border-border bg-panel p-4', className)}>
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

export function Field({ label, children, hint }: { label: ReactNode; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-muted">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  )
}

const inputCls =
  'w-full rounded-md border border-border bg-panel px-2 py-1 text-sm text-ink tabular disabled:bg-surface disabled:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50'

/**
 * Number input that keeps the user's draft while focused and commits on blur / Enter,
 * so values are not reformatted under the cursor.
 */
export function NumberInput({
  value, onCommit, dp = 2, disabled, min, max, className, ariaLabel, readOnly,
}: {
  value: number | null | undefined
  onCommit?: (v: number) => void
  dp?: number
  disabled?: boolean
  readOnly?: boolean
  min?: number
  max?: number
  className?: string
  ariaLabel?: string
}) {
  const [draft, setDraft] = useState<string | null>(null)
  const shown = draft ?? num(value ?? null, dp)
  const outOfRange = value !== null && value !== undefined && ((min !== undefined && value < min) || (max !== undefined && value > max))
  useEffect(() => {
    if (disabled) setDraft(null)
  }, [disabled])
  const commit = () => {
    if (draft === null) return
    const v = parseNum(draft)
    setDraft(null)
    if (v !== null && onCommit) onCommit(v)
  }
  return (
    <input
      type="text"
      inputMode="decimal"
      aria-label={ariaLabel}
      aria-invalid={outOfRange || undefined}
      className={clsx(inputCls, 'text-right', outOfRange && 'border-danger', readOnly && 'bg-surface', className)}
      value={shown}
      disabled={disabled}
      readOnly={readOnly}
      onFocus={() => !readOnly && setDraft(num(value ?? null, 6))}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
        if (e.key === 'Escape') setDraft(null)
      }}
    />
  )
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx(inputCls, props.className)} />
}

export function Select<T extends string>({ value, onChange, options, disabled, ariaLabel }: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
  disabled?: boolean
  ariaLabel?: string
}) {
  return (
    <select aria-label={ariaLabel} className={inputCls} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value as T)}>
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

export function Checkbox({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; disabled?: boolean }) {
  const id = useId()
  return (
    <div className="flex items-center gap-2 text-sm">
      <input id={id} type="checkbox" className="h-4 w-4 accent-[var(--accent)]" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <label htmlFor={id} className={clsx(disabled && 'text-muted')}>{label}</label>
    </div>
  )
}

export function Radio<T extends string>({ name, value, options, onChange }: { name: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div role="radiogroup" className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
      {options.map((o) => (
        <label key={o.value} className="flex cursor-pointer items-center gap-1.5">
          <input type="radio" name={name} className="accent-[var(--accent)]" checked={value === o.value} onChange={() => onChange(o.value)} />
          {o.label}
        </label>
      ))}
    </div>
  )
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'danger' | 'accent' }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        tone === 'neutral' && 'bg-surface text-muted border border-border',
        tone === 'danger' && 'bg-danger/10 text-danger border border-danger/40',
        tone === 'accent' && 'bg-accent/10 text-accent border border-accent/40',
      )}
    >
      {children}
    </span>
  )
}
