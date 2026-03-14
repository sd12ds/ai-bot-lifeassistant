/** StreakWidget — виджет текущей серии выполнения цели/привычки. */
interface Props {
  streak: number
  best?: number
  label?: string
}

export function StreakWidget({ streak, best, label = 'Серия' }: Props) {
  return (
    <div className="flex items-center gap-3 bg-orange-50 rounded-xl px-4 py-3">
      <span className="text-2xl">🔥</span>
      <div>
        <p className="text-xs text-gray-500">{label}</p>
        <p className="font-bold text-orange-600 text-lg leading-none">{streak} дней</p>
      </div>
      {best !== undefined && best > 0 && (
        <>
          <div className="w-px h-8 bg-orange-200 mx-1" />
          <div>
            <p className="text-xs text-gray-500">Рекорд</p>
            <p className="font-bold text-orange-400 text-lg leading-none">{best} дней</p>
          </div>
        </>
      )}
    </div>
  )
}
