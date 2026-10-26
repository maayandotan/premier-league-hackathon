import { type RefObject, useEffect, useState } from 'react'

/** Whether an element is (mostly) off screen: the big pitch, scrolled away. */
export function useScrolledPast(ref: RefObject<HTMLElement | null>, active: boolean): boolean {
  const [past, setPast] = useState(false)
  useEffect(() => {
    const element = ref.current
    if (!element || !active) return
    const observer = new IntersectionObserver(([entry]) => setPast(entry.intersectionRatio < 0.35),
      { threshold: [0, 0.35, 1] })
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref, active])
  return active && past
}
