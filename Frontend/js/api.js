/**
 * Cliente para todas las llamadas a la API del backend.
 * Todas las funciones retornan promesas.
 */

console.log("Cargando api.js...");
console.log("Cargando api.js...");
const BACKEND_URL = localStorage.getItem("urlApi") || "http://localhost:8000";

const Api = {
  obtenerCategorias() {
    return eventoFetch(`${BACKEND_URL}/api/productos/categorias`);
  },
  // --- AUTENTICACION ---
  iniciarSesion(correo, contrasena, tipoUsuario) {
    return eventoFetch(`${BACKEND_URL}/api/auth/login`, {
      method: "POST",
      body: JSON.stringify({ correo, contrasena, tipo_usuario: tipoUsuario }),
    });
  },

  registrar(nombre, telefono, correo, tipoUsuario, contrasena) {
    return eventoFetch(`${BACKEND_URL}/api/auth/register`, {
      method: "POST",
      body: JSON.stringify({
        nombre, telefono, correo,
        tipo_usuario: tipoUsuario, contrasena,
      }),
    });
  },

  actualizarPerfil(idUsuario, nombre, contrasena) {
    return eventoFetch(`${BACKEND_URL}/api/auth/profile`, {
      method: "PUT",
      body: JSON.stringify({
        id_usuario: idUsuario,
        nombre: nombre || undefined,
        contrasena: contrasena || undefined,
      }),
    });
  },

  // --- PRODUCTOS (VENDEDOR) ---
  listarProductosVendedor(idVendedor, pagina = 1, tamanoPagina = 20) {
    return eventoFetch(
      `${BACKEND_URL}/api/vendedor/productos?vendedor_id=${encodeURIComponent(idVendedor)}&page=${pagina}&page_size=${tamanoPagina}`
    );
  },

  crearProducto(datos) {
    return eventoFetch(`${BACKEND_URL}/api/productos`, {
      method: "POST",
      body: JSON.stringify(datos),
    });
  },

  actualizarProducto(idProducto, datos) {
    return eventoFetch(`${BACKEND_URL}/api/productos/${encodeURIComponent(idProducto)}`, {
      method: "PUT",
      body: JSON.stringify(datos),
    });
  },

  eliminarProducto(idProducto) {
    return eventoFetch(`${BACKEND_URL}/api/productos/${encodeURIComponent(idProducto)}`, {
      method: "DELETE",
    });
  },

  recomendarPrecio(marca, categoria, nombre) {
    return eventoFetch(`${BACKEND_URL}/api/productos/recomendacion-precio`, {
      method: "POST",
      body: JSON.stringify({ marca, categoria, nombre }),
    });
  },

  // --- CLIENTE ---
  listarProductosCliente(pagina = 1, busqueda = "", tamanoPagina = 12, categoria = "") {
    let url = `${BACKEND_URL}/api/cliente/productos?page=${pagina}&page_size=${tamanoPagina}`;
    if (busqueda) url += `&search=${encodeURIComponent(busqueda)}`;
    if (categoria) url += `&category=${encodeURIComponent(categoria)}`;
    return eventoFetch(url);
  },

  obtenerDetalleProducto(idProducto) {
    return eventoFetch(`${BACKEND_URL}/api/cliente/productos/${encodeURIComponent(idProducto)}`);
  },

  realizarCompra(idCliente, items, idVendedor = null) {
    return eventoFetch(`${BACKEND_URL}/api/cliente/compras`, {
      method: "POST",
      body: JSON.stringify({
        id_cliente: idCliente,
        id_vendedor: idVendedor,
        items: items.map((item) => ({
          id_producto: item.id_producto,
          cantidad: item.cantidad,
        })),
      }),
    });
  },

  listarComprasCliente(idCliente, periodo = "all", pagina = 1, tamanoPagina = 10) {
    return eventoFetch(
      `${BACKEND_URL}/api/cliente/compras?id_cliente=${encodeURIComponent(idCliente)}&period=${periodo}&page=${pagina}&page_size=${tamanoPagina}`
    );
  },

  obtenerTicketCompra(idVenta) {
    return eventoFetch(`${BACKEND_URL}/api/cliente/compras/${encodeURIComponent(idVenta)}`);
  },

  // --- VENDEDOR REPORTES ---
  obtenerIndicadoresVendedor(idVendedor = null) {
    let url = `${BACKEND_URL}/api/vendedor/reportes/indicadores`;
    if (idVendedor) url += `?id_vendedor=${encodeURIComponent(idVendedor)}`;
    return eventoFetch(url);
  },

  obtenerVentasMensuales(idVendedor = null, meses = 6) {
    let url = `${BACKEND_URL}/api/vendedor/reportes/ventas-mensuales?meses=${meses}`;
    if (idVendedor) url += `&id_vendedor=${encodeURIComponent(idVendedor)}`;
    return eventoFetch(url);
  },

  obtenerTopProductos(idVendedor = null, limite = 10) {
    let url = `${BACKEND_URL}/api/vendedor/reportes/top-productos?limite=${limite}`;
    if (idVendedor) url += `&id_vendedor=${encodeURIComponent(idVendedor)}`;
    return eventoFetch(url);
  },

  descargarReporteVentas(periodo = "all") {
    window.open(`${BACKEND_URL}/api/vendedor/reportes/ventas/csv?period=${periodo}`, "_blank");
  },
};

window.Api = Api;
