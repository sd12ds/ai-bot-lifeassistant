/**
 * Unit-тесты UI-примитивов: GlassCard, PriorityBadge, TagPill, EmptyState, FAB, Loader.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GlassCard } from '../../shared/ui/GlassCard'
import { PriorityBadge } from '../../shared/ui/PriorityBadge'
import { TagPill } from '../../shared/ui/TagPill'
import { EmptyState } from '../../shared/components/EmptyState'
import { FAB } from '../../shared/components/FAB'
import { TaskSkeletonLoader } from '../../shared/components/Loader'

// ── GlassCard ─────────────────────────────────────────────────────────────────

describe('GlassCard', () => {
  it('рендерит дочерние элементы', () => {
    render(<GlassCard><span>контент</span></GlassCard>)
    expect(screen.getByText('контент')).toBeInTheDocument()
  })

  it('применяет класс backdrop-blur', () => {
    const { container } = render(<GlassCard>x</GlassCard>)
    expect(container.firstChild).toHaveClass('backdrop-blur-xl')
  })

  it('применяет класс rounded-[20px]', () => {
    const { container } = render(<GlassCard>x</GlassCard>)
    expect(container.firstChild).toHaveClass('rounded-[20px]')
  })

  it('имеет padding по умолчанию', () => {
    const { container } = render(<GlassCard>x</GlassCard>)
    expect(container.firstChild).toHaveClass('p-4')
  })

  it('убирает padding при noPadding=true', () => {
    const { container } = render(<GlassCard noPadding>x</GlassCard>)
    expect(container.firstChild).not.toHaveClass('p-4')
  })

  it('пробрасывает className', () => {
    const { container } = render(<GlassCard className="custom-class">x</GlassCard>)
    expect(container.firstChild).toHaveClass('custom-class')
  })
})

// ── PriorityBadge ─────────────────────────────────────────────────────────────

describe('PriorityBadge', () => {
  it('рендерит красный цвет для priority=1 (высокий)', () => {
    const { container } = render(<PriorityBadge priority={1} />)
    const el = container.firstChild as HTMLElement
    expect(el.style.background).toBe('rgb(239, 68, 68)') // #ef4444
  })

  it('рендерит жёлтый цвет для priority=2 (обычный)', () => {
    const { container } = render(<PriorityBadge priority={2} />)
    const el = container.firstChild as HTMLElement
    expect(el.style.background).toBe('rgb(245, 158, 11)') // #f59e0b
  })

  it('рендерит зелёный цвет для priority=3 (низкий)', () => {
    const { container } = render(<PriorityBadge priority={3} />)
    const el = container.firstChild as HTMLElement
    expect(el.style.background).toBe('rgb(34, 197, 94)') // #22c55e
  })

  it('имеет класс absolute для позиционирования', () => {
    const { container } = render(<PriorityBadge priority={1} />)
    expect(container.firstChild).toHaveClass('absolute')
  })
})

// ── TagPill ───────────────────────────────────────────────────────────────────

describe('TagPill', () => {
  it('отображает переданный label', () => {
    render(<TagPill label="срочно" />)
    expect(screen.getByText('срочно')).toBeInTheDocument()
  })

  it('рендерит как span', () => {
    render(<TagPill label="тест" />)
    expect(screen.getByText('тест').tagName).toBe('SPAN')
  })

  it('имеет rounded-full для pill-формы', () => {
    render(<TagPill label="пилюля" />)
    expect(screen.getByText('пилюля')).toHaveClass('rounded-full')
  })
})

// ── EmptyState ────────────────────────────────────────────────────────────────

describe('EmptyState', () => {
  it('рендерит заголовок по умолчанию', () => {
    render(<EmptyState />)
    expect(screen.getByText('Задач нет')).toBeInTheDocument()
  })

  it('рендерит описание по умолчанию', () => {
    render(<EmptyState />)
    expect(screen.getByText(/Нажмите \+/)).toBeInTheDocument()
  })

  it('рендерит кастомный заголовок', () => {
    render(<EmptyState title="Ничего нет" />)
    expect(screen.getByText('Ничего нет')).toBeInTheDocument()
  })

  it('рендерит кастомное описание', () => {
    render(<EmptyState description="Добавьте что-нибудь" />)
    expect(screen.getByText('Добавьте что-нибудь')).toBeInTheDocument()
  })
})

// ── FAB ───────────────────────────────────────────────────────────────────────

describe('FAB', () => {
  it('рендерит кнопку', () => {
    render(<FAB onClick={vi.fn()} />)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('вызывает onClick при клике', () => {
    const handler = vi.fn()
    render(<FAB onClick={handler} />)
    fireEvent.click(screen.getByRole('button'))
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('позиционируется fixed', () => {
    render(<FAB onClick={vi.fn()} />)
    expect(screen.getByRole('button')).toHaveClass('fixed')
  })
})

// ── TaskSkeletonLoader ────────────────────────────────────────────────────────

describe('TaskSkeletonLoader', () => {
  it('рендерит 4 skeleton-элемента', () => {
    const { container } = render(<TaskSkeletonLoader />)
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBe(4)
  })

  it('рендерит в контейнере flex-col', () => {
    const { container } = render(<TaskSkeletonLoader />)
    expect(container.firstChild).toHaveClass('flex-col')
  })
})
