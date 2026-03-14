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
import { AuthGatePage } from './features/auth/AuthGatePage'
import { AuthRequiredPage } from './features/auth/AuthRequiredPage'
import { ProgramsPage } from './features/fitness/ProgramsPage'
import { AICoachPage } from './features/fitness/AICoachPage'
import { ProgramEditorPage } from './features/fitness/ProgramEditorPage'
// Коучинг — все экраны модуля
import { CoachingDashboard } from './features/coaching/CoachingDashboard'
import { GoalsPage }         from './features/coaching/GoalsPage'
import { GoalDetailPage }    from './features/coaching/GoalDetailPage'
import { HabitsPage }        from './features/coaching/HabitsPage'
import { CheckInPage }       from './features/coaching/CheckInPage'
import { WeeklyReviewPage }  from './features/coaching/WeeklyReviewPage'
import { InsightsPage }      from './features/coaching/InsightsPage'
import { OnboardingPage }    from './features/coaching/OnboardingPage'

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
          {/* Коучинг */}
          <Route path="/coaching"             element={<CoachingDashboard />} />
          <Route path="/coaching/goals"        element={<GoalsPage />} />
          <Route path="/coaching/goals/:id"    element={<GoalDetailPage />} />
          <Route path="/coaching/habits"       element={<HabitsPage />} />
          <Route path="/coaching/checkin"      element={<CheckInPage />} />
          <Route path="/coaching/review"       element={<WeeklyReviewPage />} />
          <Route path="/coaching/insights"     element={<InsightsPage />} />
          <Route path="/coaching/onboarding"   element={<OnboardingPage />} />
          {/* Auth */}
          <Route path="/auth"         element={<AuthGatePage />} />
          <Route path="/auth-required" element={<AuthRequiredPage />} />
          <Route path="*"             element={<Navigate to="/tasks" replace />} />
        </Routes>
      </div>

      {/* Нижняя навигация */}
      <BottomNav />
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
