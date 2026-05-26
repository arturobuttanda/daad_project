import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import AuthNavbar from "../components/AuthNavbar.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Login() {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [formValues, setFormValues] = useState({
    correo: "",
    contrasena: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isEmailValid = formValues.correo.includes("@");
  const isPasswordValid =
    formValues.contrasena.length >= 8 &&
    /[A-Z]/.test(formValues.contrasena) &&
    /\d/.test(formValues.contrasena);
  const isFormValid = isEmailValid && isPasswordValid;

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormValues((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const handleSubmit = async (event) => {
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
    <div className="page-wrap min-h-screen py-10">
      <div className="mb-8">
        <AuthNavbar title="Iniciar sesion" />
      </div>
      <div className="flex justify-center">
        <section className="glass-panel h-fit w-full max-w-2xl p-6 sm:p-8">
          
          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                Correo
              </label>
              <input
                type="email"
                className="input-field mt-2"
                placeholder="vendedor@tienda.com"
                name="correo"
                maxLength={100}
                value={formValues.correo}
                onChange={handleChange}
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
                    {showPassword ? null : <path d="M4 4l16 16" />}
                  </svg>
                </button>
              </div>
            </div>
            <div className="flex items-center justify-between text-xs text-slate-600">
              <label className="flex items-center gap-2">
                <input type="checkbox" className="h-4 w-4" />
                Recordarme
              </label>

            </div>
            <button
              type="submit"
              className="primary-button w-full disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!isFormValid || isSubmitting}
            >
              {isSubmitting ? "Ingresando..." : "Entrar al panel"}
            </button>
          </form>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
            <Link to="/registro" className="font-semibold text-ocean">
              Crear Cuenta
            </Link>

          </div>
        </section>
      </div>
    </div>
  );
}
