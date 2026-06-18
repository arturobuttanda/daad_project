/**
 * Gestion del carrito de compras del cliente.
 * Almacena en localStorage con clave "carrito_cliente_{userId}".
 */

const Carrito = {
  obtenerClave(idUsuario) {
    return `carrito_cliente_${idUsuario || "invitado"}`;
  },

  obtener(idUsuario) {
    try {
      const datos = localStorage.getItem(this.obtenerClave(idUsuario));
      return datos ? JSON.parse(datos) : [];
    } catch {
      return [];
    }
  },

  guardar(idUsuario, items) {
    localStorage.setItem(this.obtenerClave(idUsuario), JSON.stringify(items));
  },

  agregar(idUsuario, producto, cantidad = 1) {
    const items = this.obtener(idUsuario);
    const existente = items.find((item) => item.id_producto === producto.id_producto);
    if (existente) {
      existente.cantidad += cantidad;
    } else {
      items.push({
        id_producto: producto.id_producto,
        nombre: producto.nombre,
        marca: producto.marca || "",
        precio_actual: producto.precio_actual,
        cantidad: cantidad,
      });
    }
    this.guardar(idUsuario, items);
    return items;
  },

  actualizarCantidad(idUsuario, idProducto, cantidad) {
    const items = this.obtener(idUsuario);
    if (cantidad <= 0) {
      return this.quitar(idUsuario, idProducto);
    }
    const item = items.find((i) => i.id_producto === idProducto);
    if (item) item.cantidad = cantidad;
    this.guardar(idUsuario, items);
    return items;
  },

  quitar(idUsuario, idProducto) {
    let items = this.obtener(idUsuario);
    items = items.filter((i) => i.id_producto !== idProducto);
    this.guardar(idUsuario, items);
    return items;
  },

  vaciar(idUsuario) {
    localStorage.removeItem(this.obtenerClave(idUsuario));
  },

  obtenerTotal(items) {
    return items.reduce((sum, item) => {
      return sum + (item.precio_actual || 0) * item.cantidad;
    }, 0);
  },

  obtenerConteo(items) {
    return items.reduce((sum, item) => sum + item.cantidad, 0);
  },
};
