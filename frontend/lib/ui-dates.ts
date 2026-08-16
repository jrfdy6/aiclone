const UI_LOCALE = 'en-US';
const UI_TIME_ZONE = 'America/New_York';

type DateInput = Date | string | number;

const zonedPartsFormatter = new Intl.DateTimeFormat(UI_LOCALE, {
  timeZone: UI_TIME_ZONE,
  weekday: 'short',
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

const numberFormatter = new Intl.NumberFormat(UI_LOCALE);
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const;

function normalizeDateString(value: string) {
  const trimmed = value.trim();
  const timezoneAgnosticDateTime = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(\.(\d+))?$/;
  const match = trimmed.match(timezoneAgnosticDateTime);
  if (!match) {
    return trimmed;
  }

  const [, datePart, timePart, , fractionalDigits = ''] = match;
  if (fractionalDigits.length === 0) {
    return `${datePart}T${timePart}Z`;
  }

  const milliseconds = fractionalDigits.slice(0, 3).padEnd(3, '0');
  return `${datePart}T${timePart}.${milliseconds}Z`;
}

export function parseUiDate(value: DateInput) {
  const parsed =
    value instanceof Date
      ? value
      : new Date(typeof value === 'string' ? normalizeDateString(value) : value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function zonedParts(value: DateInput) {
  const parsed = parseUiDate(value);
  if (!parsed) {
    return null;
  }

  const parts = zonedPartsFormatter.formatToParts(parsed);
  const lookup = new Map(parts.map((part) => [part.type, part.value]));
  const month = Number(lookup.get('month'));
  const day = Number(lookup.get('day'));
  const hour24 = Number(lookup.get('hour'));
  const minute = lookup.get('minute');
  const weekday = lookup.get('weekday');

  if (!Number.isFinite(month) || !Number.isFinite(day) || !Number.isFinite(hour24) || !minute || !weekday || month < 1 || month > 12) {
    return null;
  }

  const hour12 = hour24 % 12 || 12;
  const period = hour24 >= 12 ? 'PM' : 'AM';

  return {
    monthName: MONTH_NAMES[month - 1],
    day,
    weekday,
    time: `${hour12}:${minute} ${period}`,
  };
}

export function formatUiTimestamp(value: DateInput) {
  const parts = zonedParts(value);
  return parts ? `${parts.monthName} ${parts.day}, ${parts.time}` : String(value);
}

export function formatUiDate(value: DateInput) {
  const parts = zonedParts(value);
  return parts ? `${parts.monthName} ${parts.day}` : String(value);
}

export function formatUiDateWithWeekday(value: DateInput) {
  const parts = zonedParts(value);
  return parts ? `${parts.weekday} ${parts.monthName} ${parts.day}` : String(value);
}

export function formatUiTime(value: DateInput) {
  const parts = zonedParts(value);
  return parts ? parts.time : String(value);
}

export function formatUiNumber(value: number) {
  return numberFormatter.format(value);
}
