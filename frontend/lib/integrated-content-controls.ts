export type VariantControlOption = {
  key: string;
  label: string;
  values: string[];
  default: string;
};

export type VariantControlState = Record<string, string>;

export function initializeVariantControls(
  options: VariantControlOption[],
  current: VariantControlState = {},
): VariantControlState {
  const allowed = new Set(options.map((option) => option.key));
  const initialized: VariantControlState = {};
  for (const option of options) {
    const candidate = current[option.key];
    initialized[option.key] = typeof candidate === 'string' && (candidate === '' || option.values.includes(candidate))
      ? candidate
      : option.default;
  }
  for (const key of Object.keys(initialized)) {
    if (!allowed.has(key)) delete initialized[key];
  }
  return initialized;
}

export function updateVariantControl(
  options: VariantControlOption[],
  current: VariantControlState,
  key: string,
  value: string,
): VariantControlState {
  const option = options.find((candidate) => candidate.key === key);
  if (!option || (value !== '' && !option.values.includes(value))) {
    throw new Error('The requested variant control is not available for this post.');
  }
  return { ...initializeVariantControls(options, current), [key]: value };
}

export function buildVariantRequestControls(
  options: VariantControlOption[],
  current: VariantControlState,
  platform: 'linkedin' | 'instagram',
): VariantControlState {
  const initialized = initializeVariantControls(options, current);
  const requested = Object.fromEntries(
    options
      .map((option) => [option.key, initialized[option.key]?.trim()] as const)
      .filter(([, value]) => Boolean(value)),
  );
  if (Object.keys(requested).length === 0) {
    requested.hook = 'direct';
  }
  if (!requested.length && platform === 'instagram' && options.some((option) => option.key === 'length')) {
    requested.length = 'short';
  }
  return requested;
}
