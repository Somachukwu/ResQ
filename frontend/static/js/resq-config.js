/**
 * ResQ Environment Configuration for GitHub Pages & Cloud Deployments
 *
 * If hosted on GitHub Pages or an external frontend, this config allows
 * pointing all API and WebSocket traffic to the deployed ResQ backend.
 */
(function () {
  const DEFAULT_REMOTE_BACKEND = "https://resq-backend-oj6j.onrender.com";
  
  // Allow manual override via localStorage: localStorage.setItem("resq_backend_url", "https://your-backend.onrender.com")
  const customBackend = localStorage.getItem("resq_backend_url") || DEFAULT_REMOTE_BACKEND;

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
})();

