import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ks_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("ks_token");
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export const formatTRY = (n) =>
  new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 2 }).format(Number(n || 0));

export const formatDate = (d) => {
  if (!d) return "-";
  try {
    const date = new Date(d.length === 10 ? d + "T00:00:00" : d);
    return date.toLocaleDateString("tr-TR", { year: "numeric", month: "2-digit", day: "2-digit" });
  } catch {
    return d;
  }
};

export const formatDateTime = (d) => {
  if (!d) return "-";
  try {
    return new Date(d).toLocaleString("tr-TR", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  } catch {
    return d;
  }
};

export const extractError = (e) => {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Beklenmeyen hata";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return JSON.stringify(d);
};
