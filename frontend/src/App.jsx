import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Inicio from "./pages/Home.jsx";
import IniciarSesion from "./pages/Login.jsx";
import Registro from "./pages/Register.jsx";
import PanelVendedor from "./pages/PanelVendedor.jsx";
import ReporteFinanciero from "./pages/ReporteFinanciero.jsx";
import PanelCliente from "./pages/PanelCliente.jsx";
import DetalleProductoCliente from "./pages/DetalleProductoCliente.jsx";
import HistorialCliente from "./pages/HistorialCliente.jsx";
import PaginaNoEncontrada from "./pages/NotFound.jsx";
import { Toaster } from "react-hot-toast";
import { EVENTO_CAMBIO_AUTENTICACION } from "./utils/authEvents.js";

function leer_snapshot_autenticacion() {
  return {
    isRegistered: localStorage.getItem("isRegistered") === "true",
    userType: localStorage.getItem("userType"),
  };
}

export default function App() {
  const [authState, setAuthState] = useState(leer_snapshot_autenticacion);

  useEffect(() => {
    const sincronizar_estado_autenticacion = () => {
      setAuthState(leer_snapshot_autenticacion());
    };

    window.addEventListener("storage", sincronizar_estado_autenticacion);
    window.addEventListener(EVENTO_CAMBIO_AUTENTICACION, sincronizar_estado_autenticacion);

    return () => {
      window.removeEventListener("storage", sincronizar_estado_autenticacion);
      window.removeEventListener(EVENTO_CAMBIO_AUTENTICACION, sincronizar_estado_autenticacion);
    };
  }, []);

  const { isRegistered, userType } = authState;
  const RequireVendor = ({ children }) =>
    isRegistered && userType === "Vendedor" ? (
      children
    ) : (
      <Navigate to="/" replace />
    );
  const RequireClient = ({ children }) =>
    isRegistered && userType === "Cliente" ? (
      children
    ) : (
      <Navigate to="/" replace />
    );

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3500,
          style: {
            borderRadius: "18px",
            background: "#fffaf2",
            color: "#0b1b2b",
            border: "1px solid rgba(11, 27, 43, 0.12)",
            boxShadow: "0 20px 40px -28px rgba(11, 27, 43, 0.5)",
          },
          success: {
            iconTheme: {
              primary: "#1a7f8f",
              secondary: "#fffaf2",
            },
          },
          error: {
            iconTheme: {
              primary: "#f26b5b",
              secondary: "#fffaf2",
            },
          },
        }}
      />
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/login" element={<IniciarSesion />} />
        <Route path="/registro" element={<Registro />} />
        <Route
          path="/vendedor"
          element={
            <RequireVendor>
              <PanelVendedor />
            </RequireVendor>
          }
        />
        <Route
          path="/vendedor/reporte"
          element={
            <RequireVendor>
              <ReporteFinanciero />
            </RequireVendor>
          }
        />
        <Route
          path="/cliente"
          element={
            <RequireClient>
              <PanelCliente />
            </RequireClient>
          }
        />
        <Route
          path="/cliente/producto/:productId"
          element={
            <RequireClient>
              <DetalleProductoCliente />
            </RequireClient>
          }
        />
        <Route
          path="/cliente/historial"
          element={
            <RequireClient>
              <HistorialCliente />
            </RequireClient>
          }
        />
        <Route
          path="*"
          element={
            isRegistered ? <PaginaNoEncontrada /> : <Navigate to="/" replace />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
