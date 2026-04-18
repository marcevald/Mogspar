import { useEffect, useRef } from 'react'

export default function useWakeLock(enabled) {
  const sentinelRef = useRef(null)

  useEffect(() => {
    if (!enabled) return
    if (typeof navigator === 'undefined' || !('wakeLock' in navigator)) return

    let cancelled = false

    const acquire = async () => {
      if (cancelled) return
      if (document.visibilityState !== 'visible') return
      if (sentinelRef.current) return
      try {
        const sentinel = await navigator.wakeLock.request('screen')
        if (cancelled) {
          sentinel.release().catch(() => {})
          return
        }
        sentinelRef.current = sentinel
        sentinel.addEventListener('release', () => {
          if (sentinelRef.current === sentinel) sentinelRef.current = null
        })
      } catch {
        // Permission denied, low battery, etc. — silently degrade.
      }
    }

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') acquire()
    }

    acquire()
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', onVisibilityChange)
      if (sentinelRef.current) {
        sentinelRef.current.release().catch(() => {})
        sentinelRef.current = null
      }
    }
  }, [enabled])
}
