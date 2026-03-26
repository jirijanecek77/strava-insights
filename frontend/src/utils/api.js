import {apiBaseUrl} from "../constants";

export function generateRequestId() {
    if (globalThis.crypto?.randomUUID) {
        return globalThis.crypto.randomUUID();
    }
    return `req-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function logFrontendRequest(level, payload) {
    const logger = level === "error" ? console.error : console.info;
    logger("[api]", payload);
}

export async function fetchJson(path, options = {}) {
    const {headers: optionHeaders, requestId = generateRequestId(), requestLabel = path, ...fetchOptions} = options;
    const url = `${apiBaseUrl}${path}`;
    const startedAt = performance.now();
    logFrontendRequest("info", {
        phase: "start",
        requestId,
        requestLabel,
        method: fetchOptions.method ?? "GET",
        url,
    });
    let response;
    try {
        response = await fetch(url, {
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
                "X-Request-ID": requestId,
                ...(optionHeaders ?? {}),
            },
            ...fetchOptions,
        });
    } catch (cause) {
        const message = cause instanceof Error && cause.message ? cause.message : "Failed to fetch";
        logFrontendRequest("error", {
            phase: "network_error",
            requestId,
            requestLabel,
            method: fetchOptions.method ?? "GET",
            message,
            url,
        });
        const error = new Error(message);
        error.cause = cause;
        error.requestId = requestId;
        error.url = url;
        throw error;
    }

    const headerRequestId = response.headers?.get?.("x-request-id");
    const responseRequestId =
        typeof headerRequestId === "string" && headerRequestId.trim() && !headerRequestId.includes("/")
            ? headerRequestId
            : requestId;

    if (!response.ok) {
        let message = `Request failed with status ${response.status}`;
        const responseType = response.headers?.get?.("content-type") ?? "";
        if (responseType.includes("application/json")) {
            try {
                const payload = await response.json();
                if (typeof payload?.detail === "string" && payload.detail.trim()) {
                    message = payload.detail;
                }
            } catch {
                // Ignore malformed error bodies and keep the status-based message.
            }
        } else {
            try {
                const text = await response.text?.();
                if (typeof text === "string" && text.trim()) {
                    message = text.trim();
                }
            } catch {
                // Ignore unreadable text bodies and keep the status-based message.
            }
        }
        logFrontendRequest("error", {
            durationMs: Math.round(performance.now() - startedAt),
            phase: "http_error",
            requestId: responseRequestId,
            requestLabel,
            method: fetchOptions.method ?? "GET",
            status: response.status,
            url,
        });
        const error = new Error(message);
        error.status = response.status;
        error.requestId = responseRequestId;
        error.url = url;
        throw error;
    }

    if (response.status === 204) {
        logFrontendRequest("info", {
            durationMs: Math.round(performance.now() - startedAt),
            phase: "success",
            requestId: responseRequestId,
            requestLabel,
            method: fetchOptions.method ?? "GET",
            status: response.status,
            url,
        });
        return null;
    }

    const payload = await response.json();
    logFrontendRequest("info", {
        durationMs: Math.round(performance.now() - startedAt),
        phase: "success",
        requestId: responseRequestId,
        requestLabel,
        method: fetchOptions.method ?? "GET",
        status: response.status,
        url,
    });
    return payload;
}
