import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import Layout from "@/components/layout/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Gelirler from "@/pages/Gelirler";
import Giderler from "@/pages/Giderler";
import Faturalar from "@/pages/Faturalar";
import Stok from "@/pages/Stok";
import AylikRapor from "@/pages/AylikRapor";
import Harcamalar from "@/pages/Harcamalar";
import Yapilacaklar from "@/pages/Yapilacaklar";
import ActivityLog from "@/pages/ActivityLog";
import Cariler from "@/pages/Cariler";
import CariDetail from "@/pages/CariDetail";
import Satislar from "@/pages/Satislar";
import GelirGider from "@/pages/GelirGider";
import "@/App.css";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="satislar" element={<Satislar />} />
            <Route path="gelir-gider" element={<GelirGider />} />
            <Route path="gelirler" element={<Gelirler />} />
            <Route path="giderler" element={<Giderler />} />
            <Route path="cariler" element={<Cariler />} />
            <Route path="cariler/:id" element={<CariDetail />} />
            <Route path="faturalar" element={<Faturalar />} />
            <Route path="stok" element={<Stok />} />
            <Route path="aylik-rapor" element={<AylikRapor />} />
            <Route path="harcamalar" element={<Harcamalar />} />
            <Route path="yapilacaklar" element={<Yapilacaklar />} />
            <Route path="islem-gunlugu" element={<ActivityLog />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
