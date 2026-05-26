const getStorageKey = (userId) => `client_cart_${userId || "guest"}`;

export function getClientCart(userId) {
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

export function setClientCart(userId, items) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(getStorageKey(userId), JSON.stringify(items));
}

export function addClientCartItem(userId, product, quantity = 1) {
  const cart = getClientCart(userId);
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
  setClientCart(userId, cart);
  return cart;
}

export function updateClientCartItem(userId, productId, quantity) {
  const cart = getClientCart(userId)
    .map((item) =>
      item.id_producto === productId
        ? { ...item, quantity }
        : item
    )
    .filter((item) => item.quantity > 0);
  setClientCart(userId, cart);
  return cart;
}

export function clearClientCart(userId) {
  setClientCart(userId, []);
}
