'use client';

import { useEffect, useState } from 'react';

type ClientLocation = {
  hash: string;
  href: string;
  pathname: string;
  search: string;
};

const LOCATION_CHANGE_EVENT = 'aiclone:locationchange';

let historyEventsPatched = false;

function readLocation(): ClientLocation {
  if (typeof window === 'undefined') {
    return { hash: '', href: '', pathname: '', search: '' };
  }
  return {
    hash: window.location.hash,
    href: window.location.href,
    pathname: window.location.pathname,
    search: window.location.search,
  };
}

function dispatchLocationChange() {
  window.dispatchEvent(new Event(LOCATION_CHANGE_EVENT));
}

function ensureHistoryEventsPatched() {
  if (typeof window === 'undefined' || historyEventsPatched) {
    return;
  }
  historyEventsPatched = true;

  const wrapHistoryMethod = (method: 'pushState' | 'replaceState') => {
    const original = window.history[method];
    window.history[method] = function patchedHistoryMethod(...args) {
      const result = original.apply(this, args);
      dispatchLocationChange();
      return result;
    };
  };

  wrapHistoryMethod('pushState');
  wrapHistoryMethod('replaceState');
  window.addEventListener('popstate', dispatchLocationChange);
  window.addEventListener('hashchange', dispatchLocationChange);
}

export function useClientLocation(): ClientLocation {
  const [location, setLocation] = useState<ClientLocation>(() => readLocation());

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    ensureHistoryEventsPatched();
    const syncLocation = () => setLocation(readLocation());
    syncLocation();
    window.addEventListener(LOCATION_CHANGE_EVENT, syncLocation);
    return () => window.removeEventListener(LOCATION_CHANGE_EVENT, syncLocation);
  }, []);

  return location;
}
