import { useQuery } from '@tanstack/react-query'
import { fetchSubscription, fetchUsage, fetchPlans } from '../../api/billing'

export function BillingDashboard() {
  const { data: sub } = useQuery({ queryKey: ['subscription'], queryFn: fetchSubscription })
  const { data: usage } = useQuery({ queryKey: ['usage'], queryFn: fetchUsage })
  const { data: plans } = useQuery({ queryKey: ['plans'], queryFn: fetchPlans })

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Billing & Usage</h1>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)]">
          <h3 className="text-sm text-[var(--text-muted)] mb-2">Подписка</h3>
          <div className="text-lg font-bold capitalize">{sub?.status || 'Нет подписки'}</div>
          {sub?.trial_end && <p className="text-sm text-[var(--text-muted)]">Trial до: {sub.trial_end.split('T')[0]}</p>}
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)]">
          <h3 className="text-sm text-[var(--text-muted)] mb-2">Использование</h3>
          {usage?.metrics ? (
            Object.entries(usage.metrics).map(([key, val]: [string, any]) => (
              <div key={key} className="flex justify-between text-sm mb-1">
                <span className="text-[var(--text-secondary)]">{key}</span>
                <span>{val.consumed} / {val.limit || '∞'}</span>
              </div>
            ))
          ) : <p className="text-sm text-[var(--text-muted)]">Нет данных</p>}
        </div>
      </div>

      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)]">
        <div className="p-4 border-b border-[var(--border)]"><h2 className="font-semibold">Тарифные планы</h2></div>
        <div className="grid grid-cols-3 gap-4 p-4">
          {plans?.map((plan: any) => (
            <div key={plan.id} className="p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border)]">
              <div className="font-bold text-lg mb-2">{plan.name}</div>
              <div className="text-2xl font-bold text-[var(--accent)] mb-3">
                {plan.price_monthly ? `${plan.price_monthly}₽/мес` : 'Бесплатно'}
              </div>
              {plan.quotas && Object.entries(plan.quotas).map(([k, v]) => (
                <div key={k} className="text-sm text-[var(--text-muted)]">{k}: {String(v)}</div>
              ))}
            </div>
          )) || <p className="text-[var(--text-muted)] col-span-3 text-center py-4">Нет тарифных планов</p>}
        </div>
      </div>
    </div>
  )
}
