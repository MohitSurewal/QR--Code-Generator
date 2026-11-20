document.addEventListener("DOMContentLoaded", () => {
  // Dismiss flash alerts smoothly
  document.querySelectorAll(".flash-close").forEach((btn) => {
    btn.addEventListener("click", () => {
      const flash = btn.closest(".flash");
      if (!flash) return;
      flash.style.transition = "opacity 0.25s ease, transform 0.25s ease";
      flash.style.opacity = "0";
      flash.style.transform = "translateY(-6px)";
      setTimeout(() => flash.remove(), 250);
    });
  });

  // Show spinner + disable double submit while uploading/generating
  document.querySelectorAll("form[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", () => {
      const submitBtn = form.querySelector("button[type='submit']");
      if (submitBtn) {
        submitBtn.classList.add("loading");
        submitBtn.disabled = true;
        const labelEl = submitBtn.querySelector(".btn-label");
        if (labelEl && submitBtn.dataset.loadingText) {
          labelEl.textContent = submitBtn.dataset.loadingText;
        }
      }
    });
  });

  // Drag-and-drop + instant photo/video preview
  document.querySelectorAll("[data-dropzone]").forEach((zone) => {
    const input = zone.querySelector("input[type='file']");
    const previewContainerId = zone.dataset.previewId;
    const fileNameLabel = zone.querySelector("[data-file-name]");
    const previewBox = previewContainerId ? document.getElementById(previewContainerId) : null;

    if (!input) return;

    zone.addEventListener("click", (e) => {
      if (e.target !== input) input.click();
    });

    ["dragenter", "dragover"].forEach((evtName) => {
      zone.addEventListener(evtName, (e) => {
        e.preventDefault();
        zone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((evtName) => {
      zone.addEventListener(evtName, (e) => {
        e.preventDefault();
        zone.classList.remove("dragover");
      });
    });

    zone.addEventListener("drop", (e) => {
      if (e.dataTransfer && e.dataTransfer.files.length > 0) {
        input.files = e.dataTransfer.files;
        handleFileChange();
      }
    });

    input.addEventListener("change", handleFileChange);

    function handleFileChange() {
      const file = input.files && input.files[0];
      if (!file) return;

      if (fileNameLabel) {
        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
        fileNameLabel.textContent = `${file.name} (${sizeMb} MB)`;
      }

      if (!previewBox) return;
      previewBox.innerHTML = "";
      const objectUrl = URL.createObjectURL(file);

      if (file.type.startsWith("image/")) {
        const img = document.createElement("img");
        img.src = objectUrl;
        img.alt = "Selected photo preview";
        previewBox.appendChild(img);
        previewBox.classList.add("visible");
      } else if (file.type.startsWith("video/")) {
        const video = document.createElement("video");
        video.src = objectUrl;
        video.controls = true;
        previewBox.appendChild(video);
        previewBox.classList.add("visible");
      } else {
        previewBox.classList.remove("visible");
      }
    }
  });

  // Copy link/asset URL to clipboard
  document.querySelectorAll("[data-copy-url]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const targetUrl = btn.dataset.copyUrl;
      if (!targetUrl) return;
      try {
        await navigator.clipboard.writeText(targetUrl);
        const original = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => {
          btn.textContent = original;
        }, 1600);
      } catch {
        btn.textContent = "Copy failed";
      }
    });
  });
});