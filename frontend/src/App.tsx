import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import RoutesPage from "./pages/Routes";
import Streams from "./pages/Streams";
import VPN from "./pages/VPN";
import Auth from "./pages/Auth";
import NginxConfig from "./pages/NginxConfig";
import Login from "./pages/Login";
import ClusterSettings from "./pages/ClusterSettings";
import Certs from "./pages/Certs";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/routes" element={<RoutesPage />} />
            <Route path="/streams" element={<Streams />} />
            <Route
              path="/vpn"
              element={
                <ProtectedRoute adminOnly>
                  <VPN />
                </ProtectedRoute>
              }
            />
            <Route
              path="/auth"
              element={
                <ProtectedRoute adminOnly>
                  <Auth />
                </ProtectedRoute>
              }
            />
            <Route
              path="/certs"
              element={
                <ProtectedRoute adminOnly>
                  <Certs />
                </ProtectedRoute>
              }
            />
            <Route
              path="/cluster-settings"
              element={
                <ProtectedRoute adminOnly>
                  <ClusterSettings />
                </ProtectedRoute>
              }
            />
            <Route
              path="/nginx"
              element={
                <ProtectedRoute adminOnly>
                  <NginxConfig />
                </ProtectedRoute>
              }
            />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
