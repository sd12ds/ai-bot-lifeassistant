import { api } from './client'
export const fetchPlans = () => api.get('/billing/plans').then(r => r.data)
export const fetchSubscription = () => api.get('/billing/subscription').then(r => r.data)
export const fetchUsage = () => api.get('/billing/usage').then(r => r.data)
export const subscribe = (planId: string) => api.post('/billing/subscribe', { plan_id: planId }).then(r => r.data)
export const upgradePlan = (planId: string) => api.post('/billing/upgrade', { plan_id: planId }).then(r => r.data)
export const cancelSubscription = () => api.post('/billing/cancel').then(r => r.data)
