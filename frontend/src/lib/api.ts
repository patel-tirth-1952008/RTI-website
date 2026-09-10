import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  register: (data: FormData) => api.post("/auth/register", data),
  login: (data: { email: string; password: string }) => api.post("/auth/login", data),
  getMe: () => api.get("/auth/me"),
  logout: (refresh_token: string) => api.post("/auth/logout", { refresh_token }),
};

export const rtiAPI = {
  generate: (formData: FormData) =>
    api.post("/rti/generate", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  list: (page = 1) => api.get(`/tracking/?page=${page}`),
  getStatus: (trackingNumber: string) => api.get(`/tracking/${trackingNumber}`),
  delete: (trackingNumber: string) => api.delete(`/rti/${trackingNumber}`),
};

export const filingAPI = {
  submit: (data: Record<string, unknown>) => api.post("/filing/submit", data),
  confirmPayment: (data: { tracking_number: string; transaction_id?: string }) =>
    api.post("/filing/confirm-payment", data),
  updateRegistration: (tracking_number: string, registration_number: string) =>
    api.post(`/filing/update-registration?tracking_number=${tracking_number}&registration_number=${registration_number}`),
  checkPortalStatus: (tracking_number: string) =>
    api.post("/filing/check-portal-status", { tracking_number }),
};

export const mediaAPI = {
  analyze: (formData: FormData) =>
    api.post("/media/analyze", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
};

export default api;