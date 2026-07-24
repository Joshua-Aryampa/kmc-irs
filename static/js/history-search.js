document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("history-search");
  const table = document.getElementById("history-table");
  if (!searchInput || !table) return;

  const rows = [...table.querySelectorAll("tbody tr.incident-row")];

  searchInput.addEventListener("input", function () {
    const needle = searchInput.value.trim().toLowerCase();
    rows.forEach((row) => {
      const haystack = (row.dataset.search || row.textContent || "").toLowerCase();
      row.hidden = needle !== "" && !haystack.includes(needle);
    });
  });
});
