import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import AuthNavbar from "../components/AuthNavbar.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const FIELD_LIMIT = 60;
const PHONE_LIMIT = 10;

export default function Register() {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [formValues, setFormValues] = useState({
    nombre: "",
    telefono: "",
    correo: "",
    tipoUsuario: "Vendedor",
    contrasena: "",
    confirmar: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isFormComplete = Object.values(formValues).every(
    (value) => value.trim().length > 0
  );
  const isEmailValid = formValues.correo.includes("@");
  const passwordChecks = {
    length: formValues.contrasena.length >= 8,
    uppercase: /[A-Z]/.test(formValues.contrasena),
    number: /\d/.test(formValues.contrasena),
  };
  const isPasswordValid = Object.values(passwordChecks).every(Boolean);
  const isPasswordMatch = formValues.contrasena === formValues.confirmar;
  const isFormValid =
    isFormComplete && isEmailValid && isPasswordValid && isPasswordMatch;

  const handleChange = (event) => {
    const { name, value } = event.target;
    const nextValue =
      name === "telefono"
        ? value.replace(/\D/g, "").slice(0, PHONE_LIMIT)
        : value.slice(0, FIELD_LIMIT);
    setFormValues((current) => ({
      ...current,
      [name]: nextValue,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }
    if (!isPasswordMatch) {
      toast.error("Las contrasenas no coinciden.");
      return;
    }
    if (!isFormValid) {
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          nombre: formValues.nombre.trim(),
          telefono: formValues.telefono.trim(),
          correo: formValues.correo.trim(),
          tipo_usuario: formValues.tipoUsuario,
          contrasena: formValues.contrasena,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo completar el registro.");
      }
      localStorage.setItem("isRegistered", "true");
      localStorage.setItem("userType", data.tipo_usuario);
      localStorage.setItem("userName", data.nombre);
      localStorage.setItem("userId", data.id);
      toast.success(`Registro completado. Bienvenido, ${data.nombre}.`);
      if (data.tipo_usuario === "Vendedor") {
        navigate("/vendedor");
      } else {
        navigate("/");
      }
    } catch (error) {
      toast.error(error.message || "No se pudo completar el registro.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-wrap min-h-screen py-10">
      <div className="mb-8">
        <AuthNavbar title="Registro de usuario" />
      </div>
      <div className="relative w-full">
        <section className="glass-panel h-fit p-8">
          <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Nombre
                </label>
                <input
                  type="text"
                  className="input-field mt-2"
                  placeholder="Nombre completo"
                  name="nombre"
                  maxLength={FIELD_LIMIT}
                  value={formValues.nombre}
                  onChange={handleChange}
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Telefono
                </label>
                <input
                  type="tel"
                  className="input-field mt-2"
                  placeholder="10 digitos"
                  name="telefono"
                  maxLength={PHONE_LIMIT}
                  inputMode="numeric"
                  pattern="[0-9]{10}"
                  value={formValues.telefono}
                  onChange={handleChange}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Correo
                </label>
                <input
                  type="email"
                  className="input-field mt-2"
                  placeholder="tu@correo.com"
                  name="correo"
                  maxLength={FIELD_LIMIT}
                  value={formValues.correo}
                  onChange={handleChange}
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Tipo de usuario
                </label>
                <select
                  className="input-field mt-2"
                  name="tipoUsuario"
                  value={formValues.tipoUsuario}
                  onChange={handleChange}
                >
                  <option>Vendedor</option>
                  <option>Cliente</option>
                </select>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Contraseña
                </label>
                <div className="relative mt-2">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="input-field pr-12"
                    placeholder="Minimo 8 caracteres"
                    name="contrasena"
                    maxLength={FIELD_LIMIT}
                    value={formValues.contrasena}
                    onChange={handleChange}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 transition hover:text-ocean"
                    aria-label={
                      showPassword ? "Ocultar contrasena" : "Mostrar contrasena"
                    }
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
                      <circle cx="12" cy="12" r="3" />
                      {showPassword ? null : (
                        <path d="M4 4l16 16" />
                      )}
                    </svg>
                  </button>
                </div>
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Confirmar
                </label>
                <div className="relative mt-2">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="input-field pr-12"
                    placeholder="Repite tu clave"
                    name="confirmar"
                    maxLength={FIELD_LIMIT}
                    value={formValues.confirmar}
                    onChange={handleChange}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 transition hover:text-ocean"
                    aria-label={
                      showPassword
                        ? "Ocultar confirmacion"
                        : "Mostrar confirmacion"
                    }
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
                      <circle cx="12" cy="12" r="3" />
                      {showPassword ? null : (
                        <path d="M4 4l16 16" />
                      )}
                    </svg>
                  </button>
                </div>
                {formValues.confirmar ? (
                  <p
                    className={
                      isPasswordMatch
                        ? "mt-2 text-xs font-semibold text-emerald-600"
                        : "mt-2 text-xs font-semibold text-rose-600"
                    }
                  >
                    {isPasswordMatch
                      ? "Las contrasenas coinciden."
                      : "Las contrasenas no coinciden."}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="rounded-2xl border border-sand bg-white/70 px-4 py-3 text-xs">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Criterios de contraseña
              </p>
              <div className="mt-2 grid gap-1">
                <span
                  className={
                    passwordChecks.length
                      ? "text-emerald-600 font-semibold"
                      : "text-rose-600 font-semibold"
                  }
                >
                  Minimo 8 caracteres
                </span>
                <span
                  className={
                    passwordChecks.uppercase
                      ? "text-emerald-600 font-semibold"
                      : "text-rose-600 font-semibold"
                  }
                >
                  Al menos una mayuscula
                </span>
                <span
                  className={
                    passwordChecks.number
                      ? "text-emerald-600 font-semibold"
                      : "text-rose-600 font-semibold"
                  }
                >
                  Al menos un numero
                </span>
              </div>
            </div>
            <button
              type="submit"
              className="primary-button w-full disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!isFormValid || isSubmitting}
            >
              {isSubmitting ? "Creando cuenta..." : "Crear cuenta"}
            </button>
          </form>
          <div className="mt-6 text-xs text-slate-600">
            Ya tienes cuenta?{" "}
            <Link to="/login" className="font-semibold text-ocean">
              Inicia sesion
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
