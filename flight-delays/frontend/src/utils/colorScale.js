export const delayLevelToColor = (level, alpha = 1) => {
  const map = {
    LOW: `rgba(34, 197, 94, ${alpha})`,
    MEDIUM: `rgba(245, 158, 11, ${alpha})`,
    HIGH: `rgba(249, 115, 22, ${alpha})`,
    SEVERE: `rgba(239, 68, 68, ${alpha})`,
    UNKNOWN: `rgba(96, 165, 250, ${alpha})`,
  };
  return map[level] ?? map.UNKNOWN;
};

export const delayMinutesToColor = (minutes, alpha = 1) => {
  if (minutes == null) return delayLevelToColor('UNKNOWN', alpha);
  if (minutes < 10) return delayLevelToColor('LOW', alpha);
  if (minutes < 25) return delayLevelToColor('MEDIUM', alpha);
  if (minutes < 45) return delayLevelToColor('HIGH', alpha);
  return delayLevelToColor('SEVERE', alpha);
};

export const delayLevelToHex = (level) => {
  const map = {
    LOW: '#22c55e',
    MEDIUM: '#f59e0b',
    HIGH: '#f97316',
    SEVERE: '#ef4444',
    UNKNOWN: '#60a5fa',
  };
  return map[level] ?? map.UNKNOWN;
};
