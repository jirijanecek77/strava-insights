import "@testing-library/jest-dom/vitest";
import {vi} from "vitest";

vi.mock("recharts", async (importOriginal) => {
    const actual = await importOriginal();
    const {cloneElement} = await import("react");

    return {
        ...actual,
        ResponsiveContainer: ({children}) => cloneElement(children, {height: 600, width: 1024}),
    };
});

const TEST_ELEMENT_BOUNDS = {
    bottom: 600,
    height: 600,
    left: 0,
    right: 1024,
    top: 0,
    width: 1024,
    x: 0,
    y: 0,
    toJSON: () => TEST_ELEMENT_BOUNDS,
};

Object.defineProperty(HTMLElement.prototype, "getBoundingClientRect", {
    configurable: true,
    value: () => TEST_ELEMENT_BOUNDS,
});

globalThis.ResizeObserver = class ResizeObserver {
    constructor(callback) {
        this.callback = callback;
    }

    observe(target) {
        this.callback([{contentRect: TEST_ELEMENT_BOUNDS, target}], this);
    }

    disconnect() {}

    unobserve() {}
};
