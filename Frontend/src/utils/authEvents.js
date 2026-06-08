export const EVENTO_CAMBIO_AUTENTICACION = "authchange";

export function notificar_cambio_autenticacion() {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new Event(EVENTO_CAMBIO_AUTENTICACION));
}