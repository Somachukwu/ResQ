/* ResQ shared theme controller.
   The zero-FOUT bootstrap runs inline in each document <head>;
   this module only wires up the toggle after DOM is ready. */

export const ThemeSwitch = {
  key: "resq-theme",

  current() {
    return document.documentElement.getAttribute("data-theme") || "light";
  },

  apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(ThemeSwitch.key, theme);
    } catch (_) {
      /* private mode — session-only theme */
    }
    document.querySelectorAll("[data-theme-toggle]").forEach((el) => {
      el.setAttribute("aria-checked", String(theme === "dark"));
      el.setAttribute(
        "aria-label",
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
      );
    });
  },

  toggle() {
    // Enable transitions only after first user interaction — keeps CLS/FOUT at zero.
    document.documentElement.classList.add("theme-anim");
    ThemeSwitch.apply(ThemeSwitch.current() === "dark" ? "light" : "dark");
  },

  mount() {
    ThemeSwitch.apply(ThemeSwitch.current());
    document.querySelectorAll("[data-theme-toggle]").forEach((el) => {
      el.addEventListener("click", ThemeSwitch.toggle);
    });
  },
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", ThemeSwitch.mount, { once: true });
} else {
  ThemeSwitch.mount();
}
