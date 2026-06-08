export const EVENTO_CAMBIO_NOTIFICACION = "notificationchange";

const STORAGE_KEY = "vendorActivityNotifications";
const MAX_NOTIFICATIONS = 20;

function emitir_cambio() {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new Event(EVENTO_CAMBIO_NOTIFICACION));
}

function obtener_almacenamiento() {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage;
}

export function leer_notificaciones() {
  const storage = obtener_almacenamiento();
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

export function agregar_notificacion(notification) {
  const storage = obtener_almacenamiento();
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

  const nextNotifications = [nextNotification, ...leer_notificaciones()].slice(0, MAX_NOTIFICATIONS);
  storage.setItem(STORAGE_KEY, JSON.stringify(nextNotifications));
  emitir_cambio();
  return nextNotification;
}

export function limpiar_notificaciones() {
  const storage = obtener_almacenamiento();
  if (!storage) {
    return;
  }

  storage.removeItem(STORAGE_KEY);
  emitir_cambio();
}
