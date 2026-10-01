/**
 * ResQ Environment Configuration for GitHub Pages & Cloud Deployments
 *
 * If hosted on GitHub Pages or an external frontend, this config allows
 * pointing all API and WebSocket traffic to the deployed ResQ backend.
 */
(function () {
  const DEFAULT_REMOTE_BACKEND = "https://resq-backend-oj6j.onrender.com";
  
  // Allow manual override via localStorage: localStorage.setItem("resq_backend_url", "https://your-backend.onrender.com")
  const customBackend = localStorage.getItem("resq_backend_url");

  // Determine current origin
  const isGitHubPages = window.location.hostname.endsWith("github.io");
  const isLocalFile = window.location.protocol === "file:";

  let apiUrl = "";
  if (customBackend) {
    apiUrl = customBackend.replace(/\/+$/, "");
  } else if (isGitHubPages || isLocalFile) {
    apiUrl = DEFAULT_REMOTE_BACKEND;
  }

  window.RESQ_CONFIG = {
    backendUrl: apiUrl,
    isGitHubPages: isGitHubPages,
    getApiEndpoint: function (path) {
      if (!path.startsWith("/")) path = "/" + path;
      return apiUrl ? apiUrl + path : path;
    }
  };

  // Keep modules using relative /api paths working from GitHub Pages without
  // changing non-API requests such as static assets and map tiles.
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    const url = typeof input === "string" && input.startsWith("/api/") && apiUrl ? apiUrl + input : input;
    const token = sessionStorage.getItem("resq_api_token");
    if (typeof url === "string" && url.includes("/api/") && token) {
      const headers = new Headers((init && init.headers) || {});
      headers.set("Authorization", `Bearer ${token}`);
      init = { ...(init || {}), headers };
    }
    return nativeFetch(url, init);
  };

  // The responder page calls io() directly. Point argument-less calls at the
  // configured backend and send its short-lived operator token when present.
  if (apiUrl && typeof window.io === "function") {
    const nativeIo = window.io;
    window.io = function (url, options) {
      if (typeof url !== "string") {
        options = url || {};
        url = apiUrl;
      }
      const token = sessionStorage.getItem("resq_api_token");
      return nativeIo(url, { ...(options || {}), auth: token ? { token } : undefined });
    };
  }
})();
