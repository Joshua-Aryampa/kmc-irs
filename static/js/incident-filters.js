document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("incident-filters");
  if (!form) return;

  function applyFilters() {
    const pageInput = form.querySelector('input[name="page"]');
    if (pageInput) {
      pageInput.remove();
    }
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
    } else {
      form.submit();
    }
  }

  form.querySelectorAll('select[name="status"], select[name="severity"]').forEach((el) => {
    el.addEventListener("change", applyFilters);
  });

  form.querySelectorAll('input[type="date"]').forEach((el) => {
    el.addEventListener("change", applyFilters);
    el.addEventListener("input", applyFilters);
  });

  const lateCheckbox = form.querySelector('input[name="late"]');
  if (lateCheckbox) {
    lateCheckbox.addEventListener("change", applyFilters);
  }
});
