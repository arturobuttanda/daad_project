/**
 * Sistema de notificaciones basado en localStorage.
 * Almacena hasta 20 notificaciones y emite eventos.
 */

const CLAVE_NOTIFICACIONES = "notificacionesVendedor";
const MAX_NOTIFICACIONES = 20;

const Notificaciones = {
  obtener() {
    try {
      const datos = localStorage.getItem(CLAVE_NOTIFICACIONES);
      return datos ? JSON.parse(datos) : [];
    } catch {
      return [];
    }
  },

  guardar(lista) {
    localStorage.setItem(CLAVE_NOTIFICACIONES, JSON.stringify(lista));
    this.emitirCambio();
  },

  agregar(notificacion) {
    const lista = this.obtener();
    lista.unshift({
      id: Date.now().toString(36) + Math.random().toString(36).substring(2, 6),
      ...notificacion,
      creadaEn: new Date().toISOString(),
    });
    if (lista.length > MAX_NOTIFICACIONES) lista.length = MAX_NOTIFICACIONES;
    this.guardar(lista);
    return lista;
  },

  limpiar() {
    localStorage.removeItem(CLAVE_NOTIFICACIONES);
    this.emitirCambio();
  },

  emitirCambio() {
    window.dispatchEvent(new Event("notificationchange"));
  },
};
