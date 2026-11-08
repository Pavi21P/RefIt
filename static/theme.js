(() => {
  let theme;
  try {
    theme = localStorage.getItem("refit-theme");
  } catch (_) {}
  document.documentElement.dataset.theme =
    theme === "dark" || theme === "light"
      ? theme
      : window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
})();
