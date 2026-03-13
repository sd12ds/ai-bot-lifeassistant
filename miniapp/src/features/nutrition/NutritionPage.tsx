/**
 * Главная страница модуля питания — дашборд.
 * CalorieRing + MacroProgressBar + WaterTracker + список MealCard + FAB.
 */
import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Settings, BarChart3 } from 'lucide-react'
import { useNutritionToday, useNutritionDay, useDeleteMeal, useLogWater } from '../../api/nutrition'
import { GlassCard } from '../../shared/ui/GlassCard'
import { Toast } from '../../shared/ui/Toast'
import { FAB } from '../../shared/components/FAB'
import { CalorieRing } from './CalorieRing'
import { MacroProgressBar } from './MacroProgressBar'
import { WaterTracker } from './WaterTracker'
import { MealCard } from './MealCard'
import { MealCreateSheet } from './MealCreateSheet'
import { GoalsSheet } from './GoalsSheet'
import { MealEditSheet } from './MealEditSheet'
import { TemplatesSheet } from './TemplatesSheet'
import { TemplateNameModal } from './TemplateNameModal'
import { useCreateTemplateFromMeal } from '../../api/nutrition'

/** Форматирует дату для отображения */
function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  const today = new Date()
  const todayStr = today.toISOString().slice(0, 10)
  if (dateStr === todayStr) return 'Сегодня'
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (dateStr === yesterday.toISOString().slice(0, 10)) return 'Вчера'
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

/** ISO дата (YYYY-MM-DD) */
function toISO(d: Date): string {
  return d.toISOString().slice(0, 10)
}

export function NutritionPage() {
  const navigate = useNavigate()
  const todayStr = toISO(new Date())

  // Навигация по дням
  const [selectedDate, setSelectedDate] = useState(todayStr)
  const isToday = selectedDate === todayStr

  // Данные — для сегодня используем /today, для других дат — собираем из meals+water+goals
  const todayQuery = useNutritionToday()
  const dayQuery = useNutritionDay(selectedDate)
  const data = isToday ? todayQuery.data : dayQuery.data
  const isLoading = isToday ? todayQuery.isLoading : dayQuery.isLoading

  const deleteMeal = useDeleteMeal()
  const logWater = useLogWater()

  // Sheets
  const [createOpen, setCreateOpen] = useState(false)
  const [goalsOpen, setGoalsOpen] = useState(false)
  const [editingMealId, setEditingMealId] = useState<number | null>(null)
  const [templatesOpen, setTemplatesOpen] = useState(false)

  // Модал сохранения шаблона — ID приёма для которого сохраняем
  const [templateMealId, setTemplateMealId] = useState<number | null>(null)
  const saveAsTemplate = useCreateTemplateFromMeal()

  // In-app toast уведомление (вместо Telegram.WebApp.showAlert)
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const clearToast = useCallback(() => setToastMsg(null), [])

  // Открыть модал ввода имени шаблона
  const handleSaveAsTemplate = (mealId: number) => {
    setTemplateMealId(mealId)
  }

  // Подтвердить сохранение шаблона
  const handleConfirmTemplate = (name: string) => {
    if (!templateMealId) return
    saveAsTemplate.mutate(
      { meal_id: templateMealId, name },
      {
        onSuccess: () => {
          // Закрываем модал и показываем in-app toast
          setTemplateMealId(null)
          setToastMsg(`Шаблон «${name}» сохранён ✅`)
        },
        onError: () => {
          setToastMsg('Ошибка сохранения шаблона ❌')
        },
      }
    )
  }

  // Навигация по дням
  const shiftDay = (delta: number) => {
    const d = new Date(selectedDate + 'T00:00:00')
    d.setDate(d.getDate() + delta)
    if (d <= new Date()) setSelectedDate(toISO(d))
  }

  // Цели (дефолтные если нет)
  const goals = data?.goals ?? { calories: 2000, protein_g: 120, fat_g: 65, carbs_g: 250, water_ml: 2000 }
  const totals = data?.totals ?? { calories: 0, protein_g: 0, fat_g: 0, carbs_g: 0 }

  return (
    <div className="flex flex-col h-full overflow-y-auto pb-24">
      {/* In-app toast уведомление */}
      <Toast message={toastMsg} onClose={clearToast} />

      {/* Шапка — дата + навигация */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <button onClick={() => shiftDay(-1)}>
          <ChevronLeft size={20} style={{ color: 'var(--app-hint)' }} />
        </button>
        <h1 className="text-base font-bold" style={{ color: 'var(--app-text)' }}>
          {formatDate(selectedDate)}
        </h1>
        <div className="flex gap-2">
          <button onClick={() => shiftDay(1)} disabled={isToday} style={{ opacity: isToday ? 0.3 : 1 }}>
            <ChevronRight size={20} style={{ color: 'var(--app-hint)' }} />
          </button>
          <button onClick={() => navigate('/nutrition/history')}>
            <BarChart3 size={18} style={{ color: 'var(--app-hint)' }} />
          </button>
          <button onClick={() => setGoalsOpen(true)}>
            <Settings size={18} style={{ color: 'var(--app-hint)' }} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm" style={{ color: 'var(--app-hint)' }}>Загрузка...</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3 px-4">
          {/* Калории — кольцо */}
          <GlassCard className="flex justify-center py-4">
            <CalorieRing consumed={totals.calories} goal={goals.calories ?? 2000} />
          </GlassCard>

          {/* БЖУ — прогресс-бары */}
          <GlassCard>
            <div className="flex flex-col gap-2">
              <MacroProgressBar label="Белки" current={totals.protein_g} goal={goals.protein_g ?? 120} color="#22c55e" />
              <MacroProgressBar label="Жиры" current={totals.fat_g} goal={goals.fat_g ?? 65} color="#f59e0b" />
              <MacroProgressBar label="Углеводы" current={totals.carbs_g} goal={goals.carbs_g ?? 250} color="#3b82f6" />
            </div>
          </GlassCard>

          {/* Вода */}
          <GlassCard>
            <WaterTracker
              current={data?.water_ml ?? 0}
              goal={goals.water_ml ?? 2000}
              onAdd={(ml) => logWater.mutate(ml)}
              loading={logWater.isPending}
            />
          </GlassCard>

          {/* Приёмы пищи */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between px-1">
              <h2 className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>Приёмы пищи</h2>
              {/* Кнопка «Из шаблона» — заметная, рядом с заголовком */}
              <button
                onClick={() => setTemplatesOpen(true)}
                className="px-3 py-1 rounded-lg text-[11px] font-medium flex items-center gap-1"
                style={{
                  color: '#818cf8',
                  background: 'rgba(99,102,241,0.12)',
                  border: '1px solid rgba(99,102,241,0.25)',
                }}
              >
                📋 Из шаблона
              </button>
            </div>
            {data?.meals && data.meals.length > 0 ? (
              data.meals.map((meal) => (
                <MealCard
                  key={meal.id}
                  meal={meal}
                  onEdit={(id) => setEditingMealId(id)}
                  onDelete={(id) => deleteMeal.mutate(id)}
                  onSaveAsTemplate={handleSaveAsTemplate}
                />
              ))
            ) : (
              <p className="text-xs text-center py-6" style={{ color: 'var(--app-hint)' }}>
                Нет приёмов пищи. Нажмите + чтобы добавить.
              </p>
            )}
          </div>
        </div>
      )}

      {/* FAB — создать приём пищи */}
      <FAB onClick={() => setCreateOpen(true)} />

      {/* Sheets */}
      <MealCreateSheet open={createOpen} onClose={() => setCreateOpen(false)} />
      <GoalsSheet open={goalsOpen} onClose={() => setGoalsOpen(false)} />
      <MealEditSheet mealId={editingMealId} onClose={() => setEditingMealId(null)} />
      <TemplatesSheet open={templatesOpen} onClose={() => setTemplatesOpen(false)} />

      {/* Модал ввода имени шаблона */}
      <TemplateNameModal
        open={templateMealId !== null}
        loading={saveAsTemplate.isPending}
        onClose={() => setTemplateMealId(null)}
        onConfirm={handleConfirmTemplate}
      />
    </div>
  )
}
