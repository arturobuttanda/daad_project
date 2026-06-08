const getStorageKey = (userId) => `client_cart_${userId || "guest"}`;

export function obtener_carrito_cliente(userId) {
  if (typeof window === "undefined") {
    return [];
  }
  const rawValue = window.localStorage.getItem(getStorageKey(userId));
  if (!rawValue) {
    return [];
  }
  try {
    const parsed = JSON.parse(rawValue);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function establecer_carrito_cliente(userId, items) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(getStorageKey(userId), JSON.stringify(items));
}

export function agregar_item_carrito_cliente(userId, product, quantity = 1) {
  const cart = obtener_carrito_cliente(userId);
  const index = cart.findIndex((item) => item.id_producto === product.id_producto);
  if (index >= 0) {
    cart[index] = {
      ...cart[index],
      quantity: cart[index].quantity + quantity,
    };
  } else {
    cart.push({
      id_producto: product.id_producto,
      nombre: product.nombre,
      marca: product.marca || "",
      precio_actual: product.precio_actual || 0,
      quantity,
    });
  }
  establecer_carrito_cliente(userId, cart);
  return cart;
}

export function actualizar_item_carrito_cliente(userId, productId, quantity) {
  const cart = obtener_carrito_cliente(userId)
    .map((item) =>
      item.id_producto === productId
        ? { ...item, quantity }
        : item
    )
    .filter((item) => item.quantity > 0);
  establecer_carrito_cliente(userId, cart);
  return cart;
}

export function vaciar_carrito_cliente(userId) {
  establecer_carrito_cliente(userId, []);
}
