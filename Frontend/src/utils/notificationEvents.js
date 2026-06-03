export const NOTIFICATION_CHANGE_EVENT = "notificationchange";

const STORAGE_KEY = "vendorActivityNotifications";
const MAX_NOTIFICATIONS = 20;

function emitChange() {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new Event(NOTIFICATION_CHANGE_EVENT));
}

function getStorage() {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage;
}

export function readNotifications() {
  const storage = getStorage();
  if (!storage) {
    return [];
  }

  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function addNotification(notification) {
  const storage = getStorage();
  if (!storage) {
    return null;
  }

  const nextNotification = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    kind: notification.kind || "activity",
    title: notification.title,
    detail: notification.detail || "",
    source: notification.source || "Sistema",
    createdAt: new Date().toISOString(),
  };

  const nextNotifications = [nextNotification, ...readNotifications()].slice(0, MAX_NOTIFICATIONS);
  storage.setItem(STORAGE_KEY, JSON.stringify(nextNotifications));
  emitChange();
  return nextNotification;
}

export function clearNotifications() {
  const storage = getStorage();
  if (!storage) {
    return;
  }

  storage.removeItem(STORAGE_KEY);
  emitChange();
}
