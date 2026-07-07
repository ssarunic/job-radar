import { useLayoutEffect } from "react";

/** Restore window scroll for a list page on return navigation (plain BrowserRouter
 * has no <ScrollRestoration>). Saves scrollY to sessionStorage on unmount; restores
 * once `ready` (data rendered, so the page has its height) and deletes the entry —
 * one-shot, so a fresh visit to the same URL starts at the top. Key by the location
 * search string so each filter combination restores its own position.
 *
 * Both effects must be layout effects: the save has to run synchronously in the
 * unmount commit, BEFORE the incoming detail page's scroll-to-top effect fires —
 * a passive-effect cleanup runs after it and records 0 (verified in the browser). */
export function useScrollRestore(key: string, ready: boolean) {
  const storageKey = `scroll:${key}`;

  useLayoutEffect(() => {
    return () => sessionStorage.setItem(storageKey, String(window.scrollY));
  }, [storageKey]);

  useLayoutEffect(() => {
    if (!ready) return;
    const saved = sessionStorage.getItem(storageKey);
    if (saved !== null) {
      sessionStorage.removeItem(storageKey);
      window.scrollTo(0, Number(saved));
    }
  }, [storageKey, ready]);
}
