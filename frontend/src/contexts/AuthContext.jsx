import { createContext, useContext, useEffect, useState } from "react";
import { api, extractError, getDeviceId } from "@/lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null); // null = checking, false = unauth
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("ks_token");
    if (!token) {
      setUser(false);
      setLoading(false);
      return;
    }
    api.get("/auth/me")
      .then((r) => { setUser(r.data); api.post("/auth/device/touch", { device_id: getDeviceId() }).catch(() => {}); })
      .catch(() => {
        localStorage.removeItem("ks_token");
        setUser(false);
      })
      .finally(() => setLoading(false));
  }, []);

  // Oturum yönetici tarafından kapatılırsa en geç 30 sn içinde girişe yönlendir
  useEffect(() => {
    if (!user) return undefined;
    const t = setInterval(() => { api.get("/auth/me").catch(() => {}); }, 30000);
    return () => clearInterval(t);
  }, [user]);

  const login = async (email, password) => {
    try {
      const { data } = await api.post("/auth/login", { email, password, device_id: getDeviceId() });
      localStorage.setItem("ks_token", data.token);
      setUser(data.user);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: extractError(e) };
    }
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("ks_token");
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
