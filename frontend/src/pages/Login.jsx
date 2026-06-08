import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import BarraAutenticacion from "../components/AuthNavbar.jsx";
import { notificar_cambio_autenticacion } from "../utils/authEvents.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function IniciarSesion() {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [selectedPortal, setSelectedPortal] = useState("Cliente");
  const [formValues, setFormValues] = useState({
    correo: "",
    contrasena: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isEmailValid = formValues.correo.includes("@");
  const isPasswordValid = formValues.contrasena.trim().length > 0;
  const isFormValid = isEmailValid && isPasswordValid;

  const manejar_cambio = (event) => {
    const { name, value } = event.target;
    setFormValues((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const manejar_envio = async (event) => {
    event.preventDefault();
    if (!isFormValid || isSubmitting) {
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          correo: formValues.correo.trim(),
          contrasena: formValues.contrasena,
          tipo_usuario: selectedPortal,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo iniciar sesion.");
      }
      localStorage.setItem("isRegistered", "true");
      localStorage.setItem("userType", data.tipo_usuario);
      localStorage.setItem("userName", data.nombre);
      localStorage.setItem("userId", data.id);
      notificar_cambio_autenticacion();
      toast.success(`Sesion iniciada. Bienvenido, ${data.nombre}.`);
      if (data.tipo_usuario === "Vendedor") {
        navigate("/vendedor");
      } else if (data.tipo_usuario === "Cliente") {
        navigate("/cliente");
      } else {
        navigate("/");
      }
    } catch (error) {
      toast.error(error.message || "No se pudo iniciar sesion.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-wrap min-h-screen py-8 sm:py-10">
      <div className="mx-auto mb-8 max-w-4xl">
        <BarraAutenticacion title="Tu portal comercial inteligente" />
      </div>

      <div className="mx-auto flex max-w-4xl justify-center">
        <section className="glass-panel relative w-full max-w-xl overflow-hidden rounded-2xl border border-[#C9D2E7] p-6 sm:p-7 md:p-8">

          <div className="relative z-10">
            <div className="flex flex-col items-center text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-ocean text-white shadow-glow">
                <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 10.5V20h16v-9.5" />
                  <path d="M3 8.5h18" />
                  <path d="M7 8.5V5.75A1.75 1.75 0 0 1 8.75 4h6.5A1.75 1.75 0 0 1 17 5.75V8.5" />
                  <path d="M9 14h6" />
                </svg>
              </div>
              <h1 className="mt-4 font-display text-3xl font-semibold text-ocean sm:text-4xl">
                NexusMarket
              </h1>
              <p className="mt-2 max-w-md text-sm text-slate-600 sm:text-base">
                Tu puerta de entrada a comercio y analitica.
              </p>
            </div>

            <div className="mt-6 rounded-xl border border-[#CFD8EA] bg-[#F8FAFF] p-1">
              <div className="grid grid-cols-2 gap-1 text-sm font-semibold text-slate-600">
                <div className="rounded-lg border border-[#C7D2FE] bg-white px-4 py-2.5 text-center text-ocean">
                  Iniciar sesión
                </div>
                <Link
                  to="/registro"
                  className="rounded-lg border border-transparent px-4 py-2.5 text-center transition hover:border-[#C7D2FE] hover:bg-white hover:text-ocean"
                >
                  Registrarse
                </Link>
              </div>
            </div>

          <form className="mt-6 space-y-4" onSubmit={manejar_envio}>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Elige tu tipo de cuenta
              </p>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setSelectedPortal("Cliente")}
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
                  onClick={() => setSelectedPortal("Vendedor")}
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

            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                Correo
              </label>
              <input
                type="email"
                className="input-field mt-2"
                placeholder={
                  selectedPortal === "Vendedor"
                    ? "vendedor_demo_01@demo.local"
                    : "cliente_demo_01@demo.local"
                }
                name="correo"
                maxLength={100}
                value={formValues.correo}
                onChange={manejar_cambio}
              />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                Contrasena
              </label>
              <div className="relative mt-2">
                <input
                  type={showPassword ? "text" : "password"}
                  className="input-field pr-12"
                  placeholder="Ingresa tu clave"
                  name="contrasena"
                  maxLength={100}
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
                    {showPassword ? null : <path d="M4 4l16 16" />}
                  </svg>
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="primary-button w-full rounded-xl py-3.5 text-base disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!isFormValid || isSubmitting}
            >
              {isSubmitting ? "Ingresando..." : "Iniciar sesión"}
            </button>
          </form>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
            <Link to="/registro" className="font-semibold text-ocean">
              Crear cuenta
            </Link>

          </div>
          </div>
        </section>
      </div>
    </div>
  );
}
