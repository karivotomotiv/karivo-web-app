import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
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
} from "lucide-react";
import { Toaster } from "@/components/ui/sonner";

const NAV = [
  { to: "/", label: "Özet", icon: LayoutDashboard, testId: "nav-dashboard", end: true },
  { to: "/gelirler", label: "Gelirler", icon: TrendingUp, testId: "nav-gelirler" },
  { to: "/giderler", label: "Giderler", icon: TrendingDown, testId: "nav-giderler" },
  { to: "/faturalar", label: "Faturalar", icon: FileText, testId: "nav-faturalar" },
  { to: "/stok", label: "Stok", icon: Package, testId: "nav-stok" },
  { to: "/harcamalar", label: "Harcamalar", icon: Wallet, testId: "nav-harcamalar" },
  { to: "/yapilacaklar", label: "Yapılacaklar", icon: ListChecks, testId: "nav-yapilacaklar" },
  { to: "/islem-gunlugu", label: "İşlem Günlüğü", icon: History, testId: "nav-logs" },
];

export default function Layout() {
  const { user, loading, logout } = useAuth();

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
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col sticky top-0 h-screen">
        <div className="px-6 py-5 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-slate-900 text-white flex items-center justify-center">
              <Building2 className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-extrabold tracking-tight text-slate-900">Şirket Yönetim</span>
              <span className="text-xs text-slate-500">v1.0</span>
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
        <div className="sticky top-0 z-10 backdrop-blur-md bg-white/90 border-b border-slate-200 px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-extrabold tracking-tight text-slate-900">
              Küçük Şirket Yönetim Paneli
            </h1>
            <div className="text-sm text-slate-500">{new Date().toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</div>
          </div>
        </div>
        <div className="p-8">
          <Outlet />
        </div>
      </main>

      <Toaster position="top-right" richColors />
    </div>
  );
}
