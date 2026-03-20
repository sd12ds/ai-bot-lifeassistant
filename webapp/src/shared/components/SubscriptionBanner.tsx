import { useQuery } from "@tanstack/react-query"
import { fetchSubscription } from "../../api/billing"

export function SubscriptionBanner() {
  const { data: sub } = useQuery({ queryKey: ["subscription"], queryFn: fetchSubscription })
  if (!sub || sub.status === "active" || sub.status === "trial") return null
  const msgs: Record<string, string> = {
    past_due: "Подписка просрочена. Оплатите для продолжения работы.",
    suspended: "Аккаунт приостановлен. Оформите подписку.",
    canceled: "Подписка отменена. Данные доступны 30 дней.",
    none: "Нет активной подписки. Оформите для начала работы.",
  }
  return (
    <div className="bg-red-900/20 border border-[var(--error)]/30 rounded-lg p-3 mb-4 text-sm text-[var(--error)]">
      {msgs[sub.status] || "Проверьте статус подписки"}
    </div>
  )
}
