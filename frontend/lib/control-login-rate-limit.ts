const LOGIN_FAILURE_LIMIT = 5;
const LOGIN_WINDOW_MS = 15 * 60 * 1000;

type LoginRateState = {
  windowStartedAt: number;
  failures: number;
  blockedUntil: number;
};

export type LoginRateStatus = {
  blocked: boolean;
  retryAfterSeconds: number;
  remainingFailures: number;
};

let state: LoginRateState = {
  windowStartedAt: 0,
  failures: 0,
  blockedUntil: 0,
};

function statusAt(now: number): LoginRateStatus {
  if (state.blockedUntil > now) {
    return {
      blocked: true,
      retryAfterSeconds: Math.max(1, Math.ceil((state.blockedUntil - now) / 1000)),
      remainingFailures: 0,
    };
  }
  if (!state.windowStartedAt || now - state.windowStartedAt >= LOGIN_WINDOW_MS) {
    state = { windowStartedAt: now, failures: 0, blockedUntil: 0 };
  } else if (state.blockedUntil) {
    state.blockedUntil = 0;
    state.failures = 0;
    state.windowStartedAt = now;
  }
  return {
    blocked: false,
    retryAfterSeconds: 0,
    remainingFailures: Math.max(0, LOGIN_FAILURE_LIMIT - state.failures),
  };
}

export function loginRateStatus(now = Date.now()): LoginRateStatus {
  return statusAt(now);
}

export function recordLoginFailure(now = Date.now()): LoginRateStatus {
  const current = statusAt(now);
  if (current.blocked) return current;
  state.failures += 1;
  if (state.failures >= LOGIN_FAILURE_LIMIT) {
    state.blockedUntil = now + LOGIN_WINDOW_MS;
  }
  return statusAt(now);
}

export function resetLoginRateLimit(): void {
  state = { windowStartedAt: 0, failures: 0, blockedUntil: 0 };
}

export { LOGIN_FAILURE_LIMIT, LOGIN_WINDOW_MS };
