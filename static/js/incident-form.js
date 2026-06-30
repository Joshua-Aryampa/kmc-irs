(function () {
  const cfg = window.INCIDENT_FORM || {};
  const form = document.getElementById("incident-form");
  if (!form) return;

  function toggleInvolveGroups() {
    document.querySelectorAll(".involve-group").forEach((section) => {
      const fieldName = section.dataset.involveField;
      const checkbox = form.querySelector(`[name="${fieldName}"]`);
      const visible = checkbox && checkbox.checked;
      section.classList.toggle("hidden", !visible);
    });
  }

  function toggleOtherText(otherBoolName) {
    const checkbox = form.querySelector(`[name="${otherBoolName}"]`);
    if (!checkbox) return;
    const wrap = checkbox.closest(".involve-group")?.querySelector(".other-text-wrap");
    if (!wrap) return;
    wrap.classList.toggle("hidden", !checkbox.checked);
  }

  Object.values(cfg.involveFields || {}).forEach((otherBool) => {
    const checkbox = form.querySelector(`[name="${otherBool}"]`);
    if (checkbox) {
      checkbox.addEventListener("change", () => toggleOtherText(otherBool));
      toggleOtherText(otherBool);
    }
  });

  form.querySelectorAll('[name^="involves_"]').forEach((el) => {
    el.addEventListener("change", toggleInvolveGroups);
  });
  toggleInvolveGroups();

  const witnessContainer = document.getElementById("witness-forms");
  const totalInput = form.querySelector(`#id_${cfg.witnessPrefix}-TOTAL_FORMS`);
  const addBtn = document.getElementById("add-witness-btn");
  const template = document.getElementById("witness-empty-form");

  function getActiveWitnessRows() {
    return [...witnessContainer.querySelectorAll(".witness-row:not(.witness-deleted)")];
  }

  function countActiveWitnessRows() {
    return getActiveWitnessRows().length;
  }

  function isFirstActiveWitnessRow(row) {
    const activeRows = getActiveWitnessRows();
    return activeRows.length > 0 && activeRows[0] === row;
  }

  function updateWitnessRemoveState() {
    getActiveWitnessRows().forEach((row, index) => {
      const deleteWrap = row.querySelector(".witness-remove-wrap");
      const removeBtn = row.querySelector(".remove-witness-btn");
      const showRemove = index > 0;
      if (deleteWrap) deleteWrap.classList.toggle("hidden", !showRemove);
      if (removeBtn) removeBtn.classList.toggle("hidden", !showRemove);
    });
  }

  function reindexWitnessRows() {
    witnessContainer.querySelectorAll(".witness-row:not(.witness-deleted)").forEach((row, index) => {
      row.dataset.formIndex = String(index);
    });
  }

  function bindRemoveButtons(scope) {
    scope.querySelectorAll(".remove-witness-btn, input[type=checkbox][name$=-DELETE]").forEach((el) => {
      if (el.dataset.bound) return;
      el.dataset.bound = "1";
      if (el.type === "checkbox") {
        el.addEventListener("change", () => {
          const row = el.closest(".witness-row");
          if (el.checked && isFirstActiveWitnessRow(row)) {
            el.checked = false;
            return;
          }
          if (el.checked) {
            row.classList.add("witness-deleted", "hidden");
            row.querySelectorAll("input:not([type=checkbox]), select, textarea").forEach((input) => {
              input.required = false;
            });
          } else {
            row.classList.remove("witness-deleted", "hidden");
          }
          updateWitnessRemoveState();
        });
      } else {
        el.addEventListener("click", () => {
          const row = el.closest(".witness-row");
          if (!row || isFirstActiveWitnessRow(row)) return;
          const deleteInput = row.querySelector('input[type=checkbox][name$="-DELETE"]');
          if (deleteInput) {
            deleteInput.checked = true;
            deleteInput.dispatchEvent(new Event("change"));
          } else {
            row.remove();
            if (totalInput) totalInput.value = String(witnessContainer.querySelectorAll(".witness-row").length);
            reindexWitnessRows();
            updateWitnessRemoveState();
          }
        });
      }
    });
  }

  if (addBtn && template && totalInput) {
    addBtn.addEventListener("click", () => {
      const index = parseInt(totalInput.value, 10);
      const html = template.innerHTML.replace(/__prefix__/g, String(index));
      const wrapper = document.createElement("div");
      wrapper.innerHTML = html.trim();
      const row = wrapper.firstElementChild;
      witnessContainer.appendChild(row);
      totalInput.value = String(index + 1);
      bindRemoveButtons(row);
      reindexWitnessRows();
      updateWitnessRemoveState();
    });
  }

  bindRemoveButtons(witnessContainer);
  updateWitnessRemoveState();

  const checkboxGroups = {};
  form.querySelectorAll('input[type=checkbox][name]').forEach((el) => {
    if (!checkboxGroups[el.name]) checkboxGroups[el.name] = [];
    checkboxGroups[el.name].push(el);
  });
  Object.values(checkboxGroups).forEach((group) => {
    if (group.length < 2) return;
    group.forEach((el) => {
      el.addEventListener("change", () => {
        group.forEach((other) => {
          other.checked = el.checked;
        });
      });
    });
  });

  const photoInput = document.getElementById("photo-input");
  const previewWrap = document.getElementById("photo-previews");
  const addPhotoBtn = document.getElementById("add-photo-btn");
  const photoCountHint = document.getElementById("photo-count-hint");
  const photoLimitMsg = document.getElementById("photo-limit-msg");
  const maxPhotos = cfg.maxPhotos || 10;
  const existingPhotoCount = cfg.existingPhotoCount || 0;
  let pendingPhotos = new DataTransfer();
  const pickerInput = document.createElement("input");
  pickerInput.type = "file";
  pickerInput.multiple = true;
  pickerInput.accept = "image/jpeg,image/png,image/webp";

  function totalPhotoCount() {
    return existingPhotoCount + pendingPhotos.files.length;
  }

  function updatePhotoHint() {
    if (!photoCountHint) return;
    photoCountHint.textContent = `${totalPhotoCount()} of ${maxPhotos} photos selected`;
    if (photoLimitMsg) photoLimitMsg.classList.add("hidden");
  }

  function syncPhotoInput() {
    if (photoInput) photoInput.files = pendingPhotos.files;
    updatePhotoHint();
  }

  function renderPhotoPreviews() {
    if (!previewWrap) return;
    previewWrap.innerHTML = "";
    Array.from(pendingPhotos.files).forEach((file, index) => {
      const card = document.createElement("div");
      card.className = "border rounded overflow-hidden relative";
      const img = document.createElement("img");
      img.className = "w-full h-24 object-cover";
      img.alt = file.name;
      img.src = URL.createObjectURL(file);
      const label = document.createElement("div");
      label.className = "text-xs p-1 truncate";
      label.textContent = file.name;
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "block w-full text-center text-xs text-red-700 py-1 border-t";
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", () => {
        const updated = new DataTransfer();
        Array.from(pendingPhotos.files).forEach((item, itemIndex) => {
          if (itemIndex !== index) updated.items.add(item);
        });
        pendingPhotos = updated;
        syncPhotoInput();
        renderPhotoPreviews();
      });
      card.appendChild(img);
      card.appendChild(label);
      card.appendChild(removeBtn);
      previewWrap.appendChild(card);
    });
  }

  if (addPhotoBtn && photoInput) {
    addPhotoBtn.addEventListener("click", () => pickerInput.click());
    pickerInput.addEventListener("change", () => {
      let limitReached = false;
      Array.from(pickerInput.files || []).forEach((file) => {
        if (totalPhotoCount() >= maxPhotos) {
          limitReached = true;
          return;
        }
        pendingPhotos.items.add(file);
      });
      pickerInput.value = "";
      syncPhotoInput();
      renderPhotoPreviews();
      if (limitReached && photoLimitMsg) {
        photoLimitMsg.textContent = `Maximum ${maxPhotos} photos allowed per incident.`;
        photoLimitMsg.classList.remove("hidden");
      }
    });
    updatePhotoHint();
  } else if (photoInput && previewWrap) {
    photoInput.addEventListener("change", () => {
      previewWrap.innerHTML = "";
      Array.from(photoInput.files || []).forEach((file) => {
        const card = document.createElement("div");
        card.className = "border rounded overflow-hidden";
        const img = document.createElement("img");
        img.className = "w-full h-24 object-cover";
        img.alt = file.name;
        img.src = URL.createObjectURL(file);
        const label = document.createElement("div");
        label.className = "text-xs p-1 truncate";
        label.textContent = file.name;
        card.appendChild(img);
        card.appendChild(label);
        previewWrap.appendChild(card);
      });
    });
  }

  const dateInput = form.querySelector('[name="incident_date"]');
  const timeInput = form.querySelector('[name="incident_time"]');
  const lateReason = document.getElementById("late-reason");
  const lateReasonError = document.getElementById("late-reason-error");
  const lateMinutes = cfg.lateMinutes ?? 30;

  function isLateSubmission() {
    if (!dateInput || !timeInput) return false;
    const dateVal = dateInput.value;
    const timeVal = timeInput.value;
    if (!dateVal || !timeVal) return false;
    const incidentAt = new Date(`${dateVal}T${timeVal}`);
    if (Number.isNaN(incidentAt.getTime())) return false;
    const diffMinutes = (Date.now() - incidentAt.getTime()) / 60000;
    return diffMinutes > lateMinutes;
  }

  function checkLate() {
    if (!lateReason) return;
    const show = isLateSubmission();
    lateReason.style.display = show ? "block" : "none";
    if (!show && lateReasonError) {
      lateReasonError.textContent = "";
      lateReasonError.classList.add("hidden");
    }
  }

  if (dateInput) {
    dateInput.addEventListener("change", checkLate);
    dateInput.addEventListener("input", checkLate);
  }
  if (timeInput) {
    timeInput.addEventListener("change", checkLate);
    timeInput.addEventListener("input", checkLate);
  }
  checkLate();

  form.addEventListener("submit", function (e) {
    const submitter = e.submitter;
    if (!submitter || submitter.name !== "action" || submitter.value !== "submit") {
      return;
    }
    checkLate();
    if (!isLateSubmission()) {
      return;
    }
    const reasonField = form.querySelector('[name="late_reason"]');
    if (reasonField && reasonField.value.trim()) {
      return;
    }
    e.preventDefault();
    if (lateReason) {
      lateReason.style.display = "block";
    }
    if (lateReasonError) {
      lateReasonError.textContent =
        `Reason for delay is required when submitting more than ${lateMinutes} minutes after the incident time.`;
      lateReasonError.classList.remove("hidden");
    }
    reasonField?.focus();
  });
})();
