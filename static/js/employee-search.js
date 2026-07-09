(function () {
  function findHidden(input, target) {
    const wrap = input.closest(".employee-search-wrap, .witness-row");
    if (wrap) {
      const scoped = wrap.querySelector('input[type="hidden"][name$="keycloak_id"]');
      if (scoped) return scoped;
    }
    const form = input.closest("form");
    if (form) {
      const inForm = form.querySelector(`#id_${target}_keycloak_id`);
      if (inForm) return inForm;
    }
    return document.getElementById(`id_${target}_keycloak_id`);
  }

  function positionList(input, list) {
    const rect = input.getBoundingClientRect();
    list.style.position = "fixed";
    list.style.left = `${rect.left}px`;
    list.style.top = `${rect.bottom + 4}px`;
    list.style.width = `${rect.width}px`;
    list.style.zIndex = "9999";
  }

  function initSearch(input) {
    const target = input.dataset.employeeTarget;
    const hidden = findHidden(input, target);
    const listId = `${target}-search-results-${input.id || target}`;
    let list = document.getElementById(listId);
    if (!list) {
      list = document.createElement("ul");
      list.id = listId;
      list.className = "employee-search-results hidden";
      document.body.appendChild(list);
    }

    let timer = null;

    function hideResults() {
      list.classList.add("hidden");
      list.innerHTML = "";
    }

    function selectEmployee(item) {
      input.value = item.name;
      const wrap = input.closest(".employee-search-wrap, .witness-row");
      const hiddenFields = wrap
        ? wrap.querySelectorAll('input[type="hidden"][name$="keycloak_id"]')
        : [];
      if (hiddenFields.length) {
        hiddenFields.forEach(function (field) {
          field.value = item.keycloak_id || "";
        });
      } else if (hidden) {
        hidden.value = item.keycloak_id || "";
      }
      if (wrap) {
        const designationInput = wrap.querySelector('input[type="hidden"][name$="-designation"]');
        if (designationInput && item.designation) {
          designationInput.value = item.designation;
        }
      }
      hideResults();
    }

    input.addEventListener("input", function () {
      if (hidden) hidden.value = "";
      const q = input.value.trim();
      clearTimeout(timer);
      if (q.length < 2) {
        hideResults();
        return;
      }
      timer = setTimeout(function () {
        fetch(`/api/employees/search/?q=${encodeURIComponent(q)}`, {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        })
          .then((r) => {
            if (!r.ok) throw new Error("Search failed");
            return r.json();
          })
          .then((data) => {
            list.innerHTML = "";
            (data.results || []).forEach((item) => {
              const li = document.createElement("li");
              li.textContent = item.name;
              li.tabIndex = 0;
              li.addEventListener("mousedown", function (e) {
                e.preventDefault();
                selectEmployee(item);
              });
              list.appendChild(li);
            });
            if (list.children.length === 0) {
              const empty = document.createElement("li");
              empty.className = "employee-search-empty";
              empty.textContent = "No employees found";
              list.appendChild(empty);
            }
            positionList(input, list);
            list.classList.remove("hidden");
          })
          .catch(() => hideResults());
      }, 250);
    });

    input.addEventListener("focus", function () {
      if (list.children.length && input.value.trim().length >= 2) {
        positionList(input, list);
        list.classList.remove("hidden");
      }
    });

    window.addEventListener(
      "scroll",
      function () {
        if (!list.classList.contains("hidden")) positionList(input, list);
      },
      true
    );

    window.addEventListener("resize", function () {
      if (!list.classList.contains("hidden")) positionList(input, list);
    });

    document.addEventListener("click", function (e) {
      if (e.target !== input && !list.contains(e.target)) hideResults();
    });
  }

  function initEmployeeSearch(scope) {
    (scope || document).querySelectorAll(".employee-search").forEach(function (input) {
      if (input.dataset.searchBound) return;
      input.dataset.searchBound = "1";
      initSearch(input);
    });
  }

  window.initEmployeeSearch = initEmployeeSearch;
  initEmployeeSearch();
})();
