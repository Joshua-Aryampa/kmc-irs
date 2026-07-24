document.addEventListener("DOMContentLoaded", function () {
  const rows = document.querySelectorAll("tr.incident-row--clickable[data-href]");
  if (!rows.length) return;

  rows.forEach(function (row) {
    row.setAttribute("tabindex", "0");
    row.setAttribute("role", "link");

    function navigate() {
      window.location.href = row.dataset.href;
    }

    row.addEventListener("click", function (e) {
      if (e.target.closest("a, button, input, select, textarea, label")) return;
      navigate();
    });

    row.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        navigate();
      }
    });
  });
});
