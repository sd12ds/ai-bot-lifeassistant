import { useState, useEffect } from 'react'
import { getToken, clearToken } from '../../api/client'

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!getToken())
  const logout = () => { clearToken(); setIsAuthenticated(false); window.location.href = '/auth' }
  useEffect(() => { setIsAuthenticated(!!getToken()) }, [])
  return { isAuthenticated, logout }
}
