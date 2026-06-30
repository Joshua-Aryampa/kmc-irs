(function () {
  const form = document.getElementById("dashboard-filters");
  if (!form) return;

  form.querySelectorAll('select[name], input[type="date"], input[name="late"]').forEach((el) => {
    el.addEventListener("change", () => form.submit());
  });
})();
