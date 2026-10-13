import { NavLink, Outlet, Navigate, useLocation } from "react-router-dom";
import { useState, useEffect, Fragment } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import SettingsDialog from "@/components/SettingsDialog";
import SampiyonWidget from "@/components/SampiyonWidget";
import {
  TrendingUp,
  TrendingDown,
  FileText,
  Package,
  Wallet,
  ListChecks,
  History,
  LogOut,
  Building2,
  LayoutDashboard,
  Settings,
  Users,
  ShoppingCart,
  Scale,
  CalendarDays,
  Menu,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Özet", icon: LayoutDashboard, testId: "nav-dashboard", end: true },
  { to: "/satislar", label: "Satışlar", icon: ShoppingCart, testId: "nav-satislar" },
  { to: "/gelir-gider", label: "Gelir / Giderler", icon: Scale, testId: "nav-gelir-gider" },
  { to: "/cariler", label: "Cariler", icon: Users, testId: "nav-cariler" },
  { to: "/faturalar", label: "Faturalar", icon: FileText, testId: "nav-faturalar" },
  { to: "/stok", label: "Stok", icon: Package, testId: "nav-stok" },
  { to: "/aylik-rapor", label: "Aylık Rapor", icon: CalendarDays, testId: "nav-aylik-rapor" },
  { to: "/harcamalar", label: "Harcamalar", icon: Wallet, testId: "nav-harcamalar" },
  { to: "/yapilacaklar", label: "Yapılacaklar", icon: ListChecks, testId: "nav-yapilacaklar" },
  { to: "/islem-gunlugu", label: "İşlem Günlüğü", icon: History, testId: "nav-logs" },
];

export default function Layout() {
  const { user, loading, logout } = useAuth();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  useEffect(() => { setMenuOpen(false); }, [location.pathname]);

  useEffect(() => {
    const onChange = () => setRefreshKey((k) => k + 1);
    window.addEventListener("karivo:data-changed", onChange);
    return () => window.removeEventListener("karivo:data-changed", onChange);
  }, []);
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-slate-500">Yükleniyor...</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      {menuOpen && <div className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" onClick={() => setMenuOpen(false)} data-testid="mobile-menu-backdrop" />}
      <aside className={`w-64 bg-white border-r border-slate-200 flex flex-col h-screen fixed lg:sticky top-0 left-0 z-40 transition-transform duration-200 lg:translate-x-0 ${menuOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="px-6 py-5 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-slate-900 text-white flex items-center justify-center">
              <Building2 className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-extrabold tracking-tight text-slate-900">Karivo Otomotiv</span>
              <span className="text-xs text-slate-500">Yönetim Paneli</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                data-testid={item.testId}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-slate-900 text-white"
                      : "text-slate-700 hover:bg-slate-100 hover:text-slate-900"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div className="p-3 border-t border-slate-200 space-y-2">
          <div className="px-3 py-2 rounded-lg bg-slate-50">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Giriş yapan
            </div>
            <div className="text-sm font-semibold text-slate-900 truncate" data-testid="current-user-name">
              {user.name}
            </div>
            <div className="text-xs text-slate-500 truncate">{user.email}</div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSettingsOpen(true)}
            className="w-full border-slate-200 text-slate-700 hover:bg-slate-100"
            data-testid="settings-btn"
          >
            <Settings className="w-4 h-4 mr-2" />
            Bildirim Ayarları
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={logout}
            className="w-full border-slate-200 text-slate-700 hover:bg-red-50 hover:text-red-700 hover:border-red-300"
            data-testid="logout-btn"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Çıkış Yap
          </Button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0">
        <div className="sticky top-0 z-20 backdrop-blur-md bg-white/90 border-b border-slate-200 px-4 sm:px-8 py-3 sm:py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <button className="lg:hidden p-2 -ml-2 rounded-lg hover:bg-slate-100" onClick={() => setMenuOpen(true)} data-testid="mobile-menu-btn" aria-label="Menü">
                <Menu className="w-5 h-5" />
              </button>
              <h1 className="text-base sm:text-xl font-extrabold tracking-tight text-slate-900 truncate">
                Karivo Otomotiv<span className="hidden sm:inline"> — Yönetim Paneli</span>
              </h1>
            </div>
            <div className="hidden md:block text-sm text-slate-500">{new Date().toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</div>
          </div>
        </div>
        <div className="p-4 sm:p-8">
          <Fragment key={refreshKey}><Outlet /></Fragment>
        </div>
      </main>

      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
      <SampiyonWidget />
    </div>
  );
}
