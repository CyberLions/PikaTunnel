import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import RoutesPage from "./pages/Routes";
import Streams from "./pages/Streams";
import VPN from "./pages/VPN";
import Auth from "./pages/Auth";
import NginxConfig from "./pages/NginxConfig";
import Login from "./pages/Login";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/routes" element={<RoutesPage />} />
          <Route path="/streams" element={<Streams />} />
          <Route path="/vpn" element={<VPN />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/nginx" element={<NginxConfig />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
