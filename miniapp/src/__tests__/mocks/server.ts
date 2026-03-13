/**
 * MSW Node-сервер для тестов (Vitest/Jest работают в Node).
 */
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
