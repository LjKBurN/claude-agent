"use client";

import { useEffect, useRef } from "react";

export function useScrollAnchor(depend: unknown) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [depend]);

  return ref;
}
