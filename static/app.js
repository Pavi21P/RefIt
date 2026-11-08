(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const toast = (message) => {
    const el = $("#toast");
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => {
      el.hidden = true;
    }, 5000);
  };
  const themeButton = $("#theme-toggle");
  const syncTheme = () =>
    themeButton.setAttribute(
      "aria-label",
      `Switch to ${document.documentElement.dataset.theme === "dark" ? "light" : "dark"} mode`,
    );
  syncTheme();
  themeButton.addEventListener("click", () => {
    const theme =
      document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("refit-theme", theme);
    } catch (_) {}
    syncTheme();
  });
  const menu = $("#menu-toggle");
  if (!$("#sidebar")) {
    menu.hidden = true;
  } else {
    menu.setAttribute("aria-expanded", String(innerWidth > 760));
    menu.addEventListener("click", () => {
      const mobile = matchMedia("(max-width: 760px)").matches;
      document.body.classList.toggle(
        mobile ? "sidebar-open" : "sidebar-hidden",
      );
      menu.setAttribute(
        "aria-expanded",
        String(
          mobile
            ? document.body.classList.contains("sidebar-open")
            : !document.body.classList.contains("sidebar-hidden"),
        ),
      );
    });
  }
  document
    .querySelectorAll("[data-dialog]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        document.getElementById(button.dataset.dialog).showModal(),
      ),
    );
  document.querySelectorAll("[data-close]").forEach((button) =>
    button.addEventListener("click", () => {
      const dialog = button.closest("dialog");
      if (dialog.dataset.busy !== "true") dialog.close();
    }),
  );
  document.querySelectorAll("dialog").forEach((dialog) =>
    dialog.addEventListener("cancel", (event) => {
      if (dialog.dataset.busy === "true") event.preventDefault();
    }),
  );
  document
    .querySelectorAll("[data-autosubmit]")
    .forEach((select) =>
      select.addEventListener("change", () => select.form.requestSubmit()),
    );
  document.querySelectorAll(".favorite-form").forEach((form) =>
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button");
      button.disabled = true;
      try {
        const result = await fetch(form.getAttribute("action"), {
          method: "POST",
          body: new FormData(form),
          headers: { Accept: "application/json" },
        });
        if (!result.ok || result.redirected) throw new Error();
        await result.json();
        location.reload();
      } catch (_) {
        toast("Could not confirm the change. Refresh to check your favorites.");
        button.disabled = false;
      }
    }),
  );
  const uploadForm = $("#upload-form");
  if (!uploadForm) return;
  const dialog = $("#upload-dialog"),
    picker = $("#image-files"),
    list = $("#upload-list"),
    submit = $("#upload-submit"),
    status = $("#upload-status");
  let queue = [],
    busy = false,
    saved = 0;
  const accepted = /\.(png|jpe?g|webp|gif|bmp|tiff?)$/i;
  const refresh = () => {
    list.replaceChildren();
    for (const entry of queue) {
      const row = document.createElement("div");
      row.className = `upload-row ${entry.state === "error" ? "error" : ""}`;
      if (entry.preview) {
        const img = document.createElement("img");
        img.src = entry.preview;
        img.alt = "";
        row.append(img);
      }
      const info = document.createElement("div");
      info.className = "file-info";
      const name = document.createElement("span");
      name.textContent = entry.file.name;
      const message = document.createElement("small");
      message.textContent =
        entry.message || `${(entry.file.size / 1024 / 1024).toFixed(1)} MB`;
      info.append(name, message);
      row.append(info);
      if (!busy && entry.state !== "saved") {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "Remove";
        remove.setAttribute("aria-label", `Remove ${entry.file.name}`);
        remove.addEventListener("click", () => {
          if (entry.preview) URL.revokeObjectURL(entry.preview);
          queue = queue.filter((item) => item !== entry);
          refresh();
        });
        row.append(remove);
      }
      list.append(row);
    }
    const pending = queue.filter((entry) => entry.state === "pending").length;
    submit.disabled = busy || !pending;
    submit.textContent = busy ? "Saving…" : "Add to library";
    status.textContent = busy
      ? `Saving ${saved + 1} of ${queue.length}…`
      : saved
        ? `${saved} saved to your library`
        : `${pending} image${pending === 1 ? "" : "s"} selected`;
  };
  const addFiles = (files) => {
    if (busy) {
      toast("Wait for the current upload to finish.");
      return;
    }
    for (const file of files) {
      if (!file.type.startsWith("image/") && !accepted.test(file.name)) {
        toast(`${file.name}: choose an image file.`);
        continue;
      }
      const tooLarge = file.size > 25 * 1024 * 1024;
      queue.push({
        file,
        state: tooLarge ? "error" : "pending",
        message: tooLarge ? "Larger than 25 MB. Resize this image first." : "",
        preview:
          !tooLarge && !/tiff|bmp/.test(file.type)
            ? URL.createObjectURL(file)
            : null,
      });
    }
    if (!dialog.open) dialog.showModal();
    refresh();
  };
  picker.addEventListener("change", () => {
    addFiles([...picker.files]);
    picker.value = "";
  });
  document.addEventListener("paste", (event) => {
    const files = [...(event.clipboardData?.files || [])];
    if (!files.length) return;
    event.preventDefault();
    addFiles(files);
  });
  let dragDepth = 0;
  const overlay = $("#page-drop-overlay");
  document.addEventListener("dragenter", (event) => {
    if (!event.dataTransfer?.types.includes("Files")) return;
    event.preventDefault();
    dragDepth++;
    if (!busy && !dialog.open) overlay.hidden = false;
  });
  document.addEventListener("dragover", (event) => {
    if (event.dataTransfer?.types.includes("Files")) {
      event.preventDefault();
      event.dataTransfer.dropEffect = busy ? "none" : "copy";
    }
  });
  document.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) overlay.hidden = true;
  });
  document.addEventListener("drop", (event) => {
    if (!event.dataTransfer?.files.length) return;
    event.preventDefault();
    overlay.hidden = true;
    dragDepth = 0;
    addFiles([...event.dataTransfer.files]);
  });
  window.addEventListener("beforeunload", (event) => {
    if (busy) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  dialog.addEventListener("close", () => {
    if (saved) location.reload();
  });
  uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    dialog.dataset.busy = "true";
    const folder = $("#upload-folder").value,
      tags = $("#upload-tags").value;
    uploadForm.querySelectorAll("input,select").forEach((input) => {
      if (input.type !== "hidden") input.disabled = true;
    });
    refresh();
    for (const entry of queue.filter((item) => item.state === "pending")) {
      entry.message = "Saving…";
      refresh();
      const data = new FormData();
      data.set("image", entry.file);
      data.set("folder", folder);
      data.set("tags", tags);
      data.set(
        "csrfmiddlewaretoken",
        uploadForm.querySelector("[name=csrfmiddlewaretoken]").value,
      );
      try {
        const response = await fetch(uploadForm.action, {
          method: "POST",
          body: data,
          headers: { Accept: "application/json" },
        });
        if (response.redirected || response.status === 403) {
          entry.state = "error";
          entry.message = "Your session expired. Reload and log in again.";
          break;
        }
        const result = await response.json();
        if (!response.ok) {
          entry.state = "error";
          entry.message =
            result.error || "Upload failed. Try again after refreshing.";
        } else {
          entry.state = "saved";
          entry.message = "Saved";
          saved++;
        }
      } catch (_) {
        entry.state = "error";
        entry.message =
          "Could not confirm upload. Refresh your library before trying again.";
        toast("Upload interrupted. Check your library before retrying.");
        break;
      }
      refresh();
    }
    busy = false;
    dialog.dataset.busy = "false";
    uploadForm.querySelectorAll("input,select").forEach((input) => {
      input.disabled = false;
    });
    refresh();
    if (queue.length && queue.every((entry) => entry.state === "saved")) {
      location.reload();
    }
  });
})();
