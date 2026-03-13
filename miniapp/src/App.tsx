/**
 * Корневой компонент приложения.
 * Роутинг, нижняя навигация, применение Telegram-темы.
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useTheme } from './shared/hooks/useTheme'
import { BottomNav } from './shared/components/BottomNav'
import { TasksPage } from './features/tasks/TasksPage'
import { CalendarPage } from './features/calendar/CalendarPage'
import { NutritionPage } from './features/nutrition/NutritionPage'
import { NutritionHistory } from './features/nutrition/NutritionHistory'
import { FitnessPage } from './features/fitness/FitnessPage'
import { WorkoutHistory } from './features/fitness/WorkoutHistory'
import { ActiveWorkout } from './features/fitness/ActiveWorkout'
import { WorkoutComplete } from './features/fitness/WorkoutComplete'
import { ProgressDashboard } from './features/fitness/ProgressDashboard'
import { BodyMetricsPage } from './features/fitness/BodyMetricsPage'
import { ProgramsPage } from './features/fitness/ProgramsPage'
import { AICoachPage } from './features/fitness/AICoachPage'
import { ProgramEditorPage } from './features/fitness/ProgramEditorPage'

// QueryClient с оптимальными настройками для мобильного приложения
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function AppContent() {
  // Применяем Telegram CSS переменные к :root при монтировании
  useTheme()

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--app-bg)' }}>
      {/* Основные маршруты */}
      <div className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Navigate to="/tasks" replace />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/calendar" element={<CalendarPage />} />
          {/* Питание */}
          <Route path="/nutrition" element={<NutritionPage />} />
          <Route path="/nutrition/history" element={<NutritionHistory />} />
          {/* Фитнес */}
          <Route path="/fitness" element={<FitnessPage />} />
          <Route path="/fitness/history" element={<WorkoutHistory />} />
          <Route path="/fitness/workout" element={<ActiveWorkout />} />
          <Route path="/fitness/complete" element={<WorkoutComplete />} />
          <Route path="/fitness/progress" element={<ProgressDashboard />} />
          <Route path="/fitness/body" element={<BodyMetricsPage />} />
          <Route path="/fitness/programs" element={<ProgramsPage />} />
          <Route path="/fitness/coach" element={<AICoachPage />} />
          <Route path="/fitness/program/:id" element={<ProgramEditorPage />} />
          {/* Заглушки */}
          <Route path="/coaching"   element={<ComingSoon label="Коучинг" />} />
          <Route path="*"           element={<Navigate to="/tasks" replace />} />
        </Routes>
      </div>

      {/* Нижняя навигация */}
      <BottomNav />
    </div>
  )
}

// Заглушка для ещё не реализованных разделов
function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full pb-24">
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center mb-4 text-3xl"
        style={{ background: 'rgba(99,102,241,0.1)' }}
      >
        🚀
      </div>
      <p className="text-lg font-bold mb-1" style={{ color: 'var(--app-text)' }}>
        {label}
      </p>
      <p className="text-sm" style={{ color: 'var(--app-hint)' }}>
        Скоро будет доступно
      </p>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
