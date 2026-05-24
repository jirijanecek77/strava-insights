const levelPriority = {
    debug: 10,
    info: 20,
    log: 20,
    warn: 30,
    error: 40,
    silent: Number.POSITIVE_INFINITY,
};

const configuredLogLevel = normalizeLogLevel(import.meta.env.VITE_LOG_LEVEL ?? "INFO");
const originalConsole = {
    debug: console.debug.bind(console),
    error: console.error.bind(console),
    info: console.info.bind(console),
    log: console.log.bind(console),
    warn: console.warn.bind(console),
};
let currentUserName = "-";

function normalizeLogLevel(level) {
    const normalized = String(level ?? "").trim().toLowerCase();
    return Object.hasOwn(levelPriority, normalized) ? normalized : "info";
}

function readableTimestamp() {
    return new Date().toISOString().replace("T", " ").replace("Z", " UTC");
}

function shouldLog(level) {
    return levelPriority[level] >= levelPriority[configuredLogLevel];
}

function prefix(level, scope) {
    const scopeLabel = scope ? ` [${scope}]` : "";
    return `${readableTimestamp()} ${level.toUpperCase()} [fe] [user=${currentUserName}]${scopeLabel}`;
}

export function logFrontend(level, scope, ...args) {
    const normalizedLevel = normalizeLogLevel(level);
    if (!shouldLog(normalizedLevel)) {
        return;
    }
    const consoleMethod = normalizedLevel === "log" ? "info" : normalizedLevel;
    originalConsole[consoleMethod](prefix(consoleMethod, scope), ...args);
}

export function setFrontendLoggerUser(user) {
    currentUserName = (user?.display_name ?? "").trim() || "-";
}

export function installFrontendConsoleLogger() {
    if (console.__stravaInsightsLoggerInstalled) {
        return;
    }

    console.__stravaInsightsLoggerInstalled = true;
    for (const method of ["debug", "info", "log", "warn", "error"]) {
        console[method] = (...args) => {
            logFrontend(method, undefined, ...args);
        };
    }
}

export const frontendLogLevel = configuredLogLevel;
