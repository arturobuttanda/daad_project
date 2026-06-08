import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import BarraAutenticacion from "../components/AuthNavbar.jsx";
import { notificar_cambio_autenticacion } from "../utils/authEvents.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const FIELD_LIMIT = 60;
const PHONE_LIMIT = 10;

export default function Registro() {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [selectedPortal, setSelectedPortal] = useState("Cliente");
  const [formValues, setFormValues] = useState({
    nombre: "",
    telefono: "",
    correo: "",
    tipoUsuario: "Cliente",
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

  const manejar_cambio = (event) => {
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

  const manejar_envio = async (event) => {
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
      notificar_cambio_autenticacion();
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
    <div className="page-wrap min-h-screen py-8 sm:py-10">
      <div className="mx-auto mb-8 max-w-4xl">
            <BarraAutenticacion title="Únete a nuestro ecosistema comercial" />
          </div>

      <div className="mx-auto flex max-w-4xl justify-center">
        <section className="glass-panel relative w-full max-w-xl overflow-hidden rounded-2xl border border-[#C9D2E7] p-6 sm:p-7 md:p-8">

          <div className="relative z-10">
            <div className="flex flex-col items-center text-center">
              <h1 className="font-display text-3xl font-semibold text-ocean sm:text-4xl">
                NexusMarket
              </h1>
              <p className="mt-2 max-w-md text-sm text-slate-600 sm:text-base">
                Crea tu cuenta de cliente o vendedor.
              </p>
            </div>

            <div className="mt-6 rounded-xl border border-[#CFD8EA] bg-[#F8FAFF] p-1">
              <div className="grid grid-cols-2 gap-1 text-sm font-semibold text-slate-600">
                <Link
                  to="/login"
                  className="rounded-lg border border-transparent px-4 py-2.5 text-center transition hover:border-[#C7D2FE] hover:bg-white hover:text-ocean"
                >
                  Iniciar sesión
                </Link>
                <div className="rounded-lg border border-[#C7D2FE] bg-white px-4 py-2.5 text-center text-ocean">
                  Registrarse
                </div>
              </div>
            </div>

          <form className="mt-6 grid gap-4" onSubmit={manejar_envio}>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Elige tu tipo de cuenta
              </p>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedPortal("Cliente");
                    setFormValues((current) => ({ ...current, tipoUsuario: "Cliente" }));
                  }}
                  className={
                    selectedPortal === "Cliente"
                      ? "flex items-center justify-center gap-2 rounded-xl border border-ocean bg-[#EFF4FF] px-4 py-3 text-sm font-semibold text-ocean transition"
                      : "flex items-center justify-center gap-2 rounded-xl border border-[#CFD8EA] bg-[#F2F6FF] px-4 py-3 text-sm font-semibold text-slate-600 transition hover:border-[#9FB3E8] hover:bg-white"
                  }
                >
                  Cliente
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedPortal("Vendedor");
                    setFormValues((current) => ({ ...current, tipoUsuario: "Vendedor" }));
                  }}
                  className={
                    selectedPortal === "Vendedor"
                      ? "flex items-center justify-center gap-2 rounded-xl border border-ocean bg-[#EFF4FF] px-4 py-3 text-sm font-semibold text-ocean transition"
                      : "flex items-center justify-center gap-2 rounded-xl border border-[#CFD8EA] bg-[#F2F6FF] px-4 py-3 text-sm font-semibold text-slate-600 transition hover:border-[#9FB3E8] hover:bg-white"
                  }
                >
                  Vendedor
                </button>
              </div>
            </div>

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
                  onChange={manejar_cambio}
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
                  onChange={manejar_cambio}
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
                  onChange={manejar_cambio}
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Tipo de usuario
                </label>
                <input
                  type="text"
                  className="input-field mt-2"
                  value={formValues.tipoUsuario}
                  readOnly
                />
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
                    onChange={manejar_cambio}
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
                    onChange={manejar_cambio}
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
              className="secondary-button w-full disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!isFormValid || isSubmitting}
            >
              {isSubmitting ? "Creando cuenta..." : "Crear cuenta"}
            </button>
          </form>
          <div className="mt-6 text-xs text-slate-600">
            Ya tienes cuenta?{" "}
            <Link to="/login" className="font-semibold text-ocean">
              Inicia sesión
            </Link>
          </div>
          </div>
        </section>
      </div>
    </div>
  );
}
