import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { fetchPlans, subscribe } from "../../api/billing"

export function PlanSelector() {
  const qc = useQueryClient()
  const { data: plans } = useQuery({ queryKey: ["plans"], queryFn: fetchPlans })
  const subMut = useMutation({ mutationFn: (planId: string) => subscribe(planId), onSuccess: () => qc.invalidateQueries({ queryKey: ["subscription"] }) })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Тарифные планы</h1>
      <div className="grid grid-cols-3 gap-4">
        {plans?.map((p: any) => (
          <div key={p.id} className="bg-[var(--bg-card)] rounded-xl p-6 border border-[var(--border)] space-y-3">
            <div className="text-xl font-bold">{p.name}</div>
            <div className="text-3xl font-bold text-[var(--accent)]">{p.price_monthly ? `${p.price_monthly}₽` : "Free"}<span className="text-sm font-normal text-[var(--text-muted)]">/мес</span></div>
            {p.quotas && Object.entries(p.quotas).map(([k, v]) => <div key={k} className="text-sm text-[var(--text-secondary)]">{k}: {String(v)}</div>)}
            <button onClick={() => subMut.mutate(p.id)} className="w-full py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-lg text-sm font-medium">Выбрать</button>
          </div>
        )) || <p className="text-[var(--text-muted)] col-span-3 text-center">Нет планов</p>}
      </div>
    </div>
  )
}
