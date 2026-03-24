/** SchedulePicker — визуальный выбор интервала парсинга (без cron). */
interface Option { label: string; hours: number }
interface Props {
  value: number   // interval_hours
  onChange: (hours: number) => void
}

const OPTIONS: Option[] = [
  { label: '1ч',  hours: 1  },
  { label: '6ч',  hours: 6  },
  { label: '12ч', hours: 12 },
  { label: '1д',  hours: 24 },
  { label: '7д',  hours: 168 },
]

export function SchedulePicker({ value, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {OPTIONS.map(opt => (
        <button
          key={opt.hours}
          onClick={() => onChange(opt.hours)}
          className={`flex-1 py-1.5 text-xs font-medium rounded-lg border transition-colors
            ${value === opt.hours
              ? 'bg-[var(--accent)]/20 text-[var(--accent)] border-[var(--accent)]'
              : 'text-[var(--text-muted)] border-[var(--border)] hover:bg-[var(--bg-hover)]'
            }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
