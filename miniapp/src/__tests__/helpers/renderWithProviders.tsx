/**
 * Хелпер: оборачивает компонент во все нужные провайдеры (Router, QueryClient).
 */
import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

interface Options { initialRoute?: string }

export function renderWithProviders(ui: ReactElement, { initialRoute = '/' }: Options = {}) {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  )
}
