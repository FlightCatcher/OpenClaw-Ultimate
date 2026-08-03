function numericTimestamp(message) {
  const value = Number(message?.timestamp ?? 0);
  return Number.isFinite(value) ? value : 0;
}

export function latestMessageByRole(messages, role) {
  let latest = null;
  let latestTimestamp = Number.NEGATIVE_INFINITY;
  for (const message of messages ?? []) {
    if (message?.role !== role) continue;
    const timestamp = numericTimestamp(message);
    if (latest === null || timestamp >= latestTimestamp) {
      latest = message;
      latestTimestamp = timestamp;
    }
  }
  return latest;
}
