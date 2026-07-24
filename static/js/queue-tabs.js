document.addEventListener("DOMContentLoaded", function () {
  const tabs = document.querySelectorAll("[data-queue-tab]");
  const panels = document.querySelectorAll("[data-queue-panel]");
  if (!tabs.length || !panels.length) return;

  function activate(tabName) {
    tabs.forEach((tab) => {
      const active = tab.dataset.queueTab === tabName;
      tab.classList.toggle("queue-tab--active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    panels.forEach((panel) => {
      const active = panel.dataset.queuePanel === tabName;
      panel.classList.toggle("queue-panel--active", active);
      panel.hidden = !active;
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activate(tab.dataset.queueTab));
  });
});
