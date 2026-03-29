import { format, formatDistanceToNow, parseISO } from 'date-fns';

export const formatTime = (isoString) => {
  if (!isoString) return '--:--';
  try {
    return format(parseISO(isoString), 'HH:mm');
  } catch {
    return '--:--';
  }
};

export const formatDate = (isoString) => {
  if (!isoString) return '';
  try {
    return format(parseISO(isoString), 'MMM dd, yyyy');
  } catch {
    return '';
  }
};

export const formatDateTime = (isoString) => {
  if (!isoString) return '';
  try {
    return format(parseISO(isoString), 'MMM dd HH:mm');
  } catch {
    return '';
  }
};

export const formatRelative = (isoString) => {
  if (!isoString) return '';
  try {
    return formatDistanceToNow(parseISO(isoString), { addSuffix: true });
  } catch {
    return '';
  }
};

export const formatPct = (value) => {
  if (value == null) return 'N/A';
  return `${(value * 100).toFixed(1)}%`;
};

export const formatDelay = (minutes) => {
  if (minutes == null) return 'N/A';
  if (minutes <= 0) return 'On time';
  return `${Math.round(minutes)} min`;
};

export const formatNumber = (num) => {
  if (num == null) return 'N/A';
  return num.toLocaleString();
};
