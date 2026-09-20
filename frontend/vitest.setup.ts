import "@testing-library/jest-dom/vitest";

if (typeof globalThis.matchMedia === "undefined") {
  globalThis.matchMedia = (() => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
    media: "",
    onchange: null,
  })) as (query: string) => MediaQueryList;
}