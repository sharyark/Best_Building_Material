import '@testing-library/jest-dom/vitest'

// antd (rc-util) expects these browser APIs; jsdom doesn't ship them.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false, media: query, onchange: null,
    addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
  }),
})
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (ResizeObserverStub as unknown as typeof ResizeObserver)
if (!globalThis.crypto?.randomUUID) {
  Object.defineProperty(globalThis, 'crypto', { value: { randomUUID: () => '00000000-0000-4000-8000-000000000000' } })
}

// jsdom logs "not implemented" for the pseudo-element form antd's table scroll code uses.
const realGetComputedStyle = window.getComputedStyle.bind(window)
window.getComputedStyle = (el: Element) => realGetComputedStyle(el)
