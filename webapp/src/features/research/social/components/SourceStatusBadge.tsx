/** SourceStatusBadge — статус источника: active / paused / error / running. */
interface Props { status: string }

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  active:  { label: 'активен',  cls: 'bg-green-600 text-white' },
  paused:  { label: 'пауза',    cls: 'bg-gray-600 text-white' },
  error:   { label: 'ошибка',   cls: 'bg-red-600 text-white' },
  running: { label: 'запущен',  cls: 'bg-blue-600 text-white' },
}

export function SourceStatusBadge({ status }: Props) {
  const cfg = STATUS_MAP[status] ?? { label: status, cls: 'bg-gray-600 text-white' }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}
