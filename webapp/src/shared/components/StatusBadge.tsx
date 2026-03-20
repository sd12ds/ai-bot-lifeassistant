export function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    draft: 'bg-gray-600', pending: 'bg-yellow-600', running: 'bg-blue-600',
    completed: 'bg-green-600', failed: 'bg-red-600', canceled: 'bg-gray-500',
    queued: 'bg-yellow-500', archived: 'bg-gray-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium text-white ${colors[status] || 'bg-gray-600'}`}>
      {status}
    </span>
  )
}
