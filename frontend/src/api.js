import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 120000,
});

export function setToastHandler(fn) {
  api.__toast = fn;
}

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg = err.response?.data?.message || err.message || "Request failed";
    if (api.__toast) api.__toast(msg, "error");
    return Promise.reject(err);
  }
);

export const Papers = {
  list: () => api.get("/papers").then((r) => r.data),
  get: (id) => api.get(`/papers/${id}`).then((r) => r.data),
  status: (id) => api.get(`/papers/${id}/status`).then((r) => r.data),
  delete: (id) => api.delete(`/papers/${id}`).then((r) => r.data),
  upload: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post("/papers/upload", fd).then((r) => r.data);
  },
  arxivSearch: (q) => api.get("/papers/arxiv/search", { params: { q } }).then((r) => r.data),
  importArxiv: (arxiv_id) => api.post("/papers/import-arxiv", { arxiv_id }).then((r) => r.data),
  discover: (query, sources, maxPer = 15) =>
    api.post("/papers/discover", { query, sources, max_per_source: maxPer }).then((r) => r.data),
  importBulk: (items, delaySec = 1.5) =>
    api.post("/papers/import-bulk", { items, delay_sec: delaySec }).then((r) => r.data),
  similar: (id) => api.get(`/papers/${id}/similar`).then((r) => r.data),
  summarize: (id, regenerate = false) =>
    api.post(`/papers/${id}/summarize`, null, { params: { regenerate } }).then((r) => r.data),
  keywords: (id) => api.get(`/papers/${id}/keywords`).then((r) => r.data),
};

export const Search = {
  query: (params) => api.get("/search", { params }).then((r) => r.data),
};

export const Analyze = {
  topics: () => api.get("/topics").then((r) => r.data),
  compare: (a, b) => api.post("/compare", { paper_ids: [a, b] }).then((r) => r.data),
};

export const QA = {
  ask: (payload) => api.post("/qa", payload).then((r) => r.data),
  history: (paper_id) =>
    api.get("/qa/history", { params: paper_id ? { paper_id } : {} }).then((r) => r.data),
  streamUrl: (question, paper_id) => {
    const base = import.meta.env.VITE_API_BASE_URL || "/api";
    const root = base.startsWith("http") ? base.replace(/\/$/, "") : `${window.location.origin}/api`;
    const u = new URL(`${root}/qa/stream`);
    u.searchParams.set("question", question);
    if (paper_id) u.searchParams.set("paper_id", paper_id);
    return u.toString();
  },
};

export default api;
