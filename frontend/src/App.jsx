import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Home from "./pages/Home.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import VendorDashboard from "./pages/VendorDashboard.jsx";
import FinancialReport from "./pages/FinancialReport.jsx";
import ClientDashboard from "./pages/ClientDashboard.jsx";
import ClientProductDetail from "./pages/ClientProductDetail.jsx";
import ClientHistory from "./pages/ClientHistory.jsx";
import NotFound from "./pages/NotFound.jsx";
import { Toaster } from "react-hot-toast";

export default function App() {
  const isRegistered = localStorage.getItem("isRegistered") === "true";
  const userType = localStorage.getItem("userType");
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
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/registro" element={<Register />} />
        <Route
          path="/vendedor"
          element={
            <RequireVendor>
              <VendorDashboard />
            </RequireVendor>
          }
        />
        <Route
          path="/vendedor/reporte"
          element={
            <RequireVendor>
              <FinancialReport />
            </RequireVendor>
          }
        />
        <Route
          path="/cliente"
          element={
            <RequireClient>
              <ClientDashboard />
            </RequireClient>
          }
        />
        <Route
          path="/cliente/producto/:productId"
          element={
            <RequireClient>
              <ClientProductDetail />
            </RequireClient>
          }
        />
        <Route
          path="/cliente/historial"
          element={
            <RequireClient>
              <ClientHistory />
            </RequireClient>
          }
        />
        <Route
          path="*"
          element={
            isRegistered ? <NotFound /> : <Navigate to="/" replace />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
