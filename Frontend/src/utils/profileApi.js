const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function updateUserProfile({ userId, userName, password }) {
  const payload = {
    id_usuario: userId,
  };

  if (typeof userName === "string") {
    payload.nombre = userName;
  }

  if (typeof password === "string") {
    payload.contrasena = password;
  }

  const response = await fetch(`${API_URL}/api/auth/profile`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "No se pudo actualizar el perfil.");
  }

  return data;
}
