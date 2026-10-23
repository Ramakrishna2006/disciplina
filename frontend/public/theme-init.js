// Runs before the page is drawn, so a dark-mode user never sees a white flash.
// It is a separate file (not inline in index.html) because our Content-Security-Policy
// only allows scripts from our own files: script-src 'self'.
;(function () {
  var choice = "system"
  try {
    choice = localStorage.getItem("disciplina-theme") || "system"
  } catch (e) {
    /* storage blocked (private mode): fall back to the system setting */
  }
  var dark = choice === "dark" || (choice === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.toggle("dark", dark)
})()
