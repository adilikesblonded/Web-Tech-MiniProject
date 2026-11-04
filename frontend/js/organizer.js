let clubs = [];
let clubId = null;
let events = [];
let selectedId = null;
let editing = null;
let scanner = null;
let lastScan = { token: "", at: 0 };

const eventModal = new bootstrap.Modal($("#event-modal"));
const form = $("#event-form");
CATEGORIES.forEach((c) => $("#f-category").append(h("option", { value: c, text: c })));

/* ---------- Events table ---------- */
async function loadEvents() {
  const holder = $("#event-table");
  holder.replaceChildren(loading("Loading events…"));
  try {
    events = await api(`/organizer/events?club_id=${clubId}`);
    renderTable();
    if (selectedId && events.some((e) => e.id === selectedId)) loadPanel();
  } catch (err) {
    holder.replaceChildren(errorBox(err.message, loadEvents));
  }
}

function renderTable() {
  const holder = $("#event-table");
  if (!events.length) {
    holder.replaceChildren(emptyState("This club has no events yet.",
      h("button", { class: "btn btn-sm btn-primary", type: "button", text: "Create the first event", onclick: () => openForm(null) })));
    return;
  }
  holder.replaceChildren(h("table", { class: "table align-middle" },
    h("thead", {}, h("tr", {},
      ["Event", "Date", "Status", "Seats", "Waitlist", ""].map((t) => h("th", { scope: "col", text: t })))),
    h("tbody", {}, events.map((e) => {
      const editable = e.status === "published" && e.phase === "upcoming";
      const cancellable = e.status === "published" && e.phase !== "past";
      return h("tr", { class: e.id === selectedId ? "table-active" : null },
        h("td", {}, h("span", { class: "fw-semibold", text: e.title })),
        h("td", { class: "text-nowrap", text: fmtDateTime(e.starts_at) }),
        h("td", {}, statusLabel(e.status === "cancelled" ? "Cancelled" : e.phase === "past" ? "Ended" : e.availability)),
        h("td", { text: `${e.confirmed} / ${e.capacity}` }),
        h("td", { text: String(e.waitlisted) }),
        h("td", { class: "text-end text-nowrap" },
          h("button", { class: "btn btn-sm btn-success", type: "button", text: "Manage", onclick: () => select(e.id) }), " ",
          editable ? h("button", { class: "btn btn-sm btn-outline-dark", type: "button", text: "Edit", onclick: () => openForm(e) }) : null, " ",
          cancellable ? h("button", { class: "btn btn-sm btn-link link-danger", type: "button", text: "Cancel", onclick: (ev) => cancelEvent(e, ev.currentTarget) }) : null));
    }))));
}

async function cancelEvent(e, button) {
  if (!confirm(`Cancel "${e.title}"? Registered students will see it as cancelled.`)) return;
  try {
    await withBusy(button, () => api(`/events/${e.id}/cancel`, { method: "POST" }));
    toast("Event cancelled.");
    loadEvents();
  } catch (err) {
    toast(err.message, "danger");
  }
}

/* ---------- Selected event: totals, participants, check-in ---------- */
function select(id) {
  selectedId = id;
  history.replaceState(null, "", `?club=${clubId}&event=${id}`);
  renderTable();
  loadPanel();
  $("#event-panel").scrollIntoView({ behavior: "smooth" });
}

function stat(label, value) {
  return h("div", { class: "col-6 col-md-3" },
    h("div", { class: "surface stat" }, h("div", { class: "n", text: String(value) }), h("div", { class: "l", text: label })));
}

async function loadPanel() {
  const panel = $("#event-panel");
  panel.hidden = false;
  $("#participants").replaceChildren(loading());
  try {
    const data = await api(`/events/${selectedId}/participants`);
    const s = data.summary;
    $("#panel-title").textContent = data.event.title;
    $("#panel-link").href = `event.html?id=${selectedId}`;
    $("#stats").replaceChildren(stat("Confirmed", s.confirmed), stat("Waitlisted", s.waitlisted),
      stat("Checked in", s.checked_in), stat("Seats remaining", s.seats_left));
    $("#attendance-text").textContent = `${s.checked_in} of ${s.confirmed} confirmed · ${s.attendance_pct}%`;
    $("#attendance-bar").setAttribute("aria-valuenow", s.attendance_pct);
    $("#attendance-bar .progress-bar").style.width = `${s.attendance_pct}%`;

    $("#participants").replaceChildren(data.participants.length
      ? h("table", { class: "table table-sm align-middle mb-0" },
          h("thead", {}, h("tr", {}, ["Name", "Reg. no.", "Email", "Status", "Checked in"].map((t) => h("th", { scope: "col", text: t })))),
          h("tbody", {}, data.participants.map((p) => h("tr", {},
            h("td", { text: p.name }), h("td", { text: p.reg_no }), h("td", { text: p.email }),
            h("td", {}, statusLabel(p.status === "waitlisted" ? `Waitlisted · #${p.position}` : "Confirmed")),
            h("td", { text: p.checked_in_at ? fmtTime(p.checked_in_at) : "—" })))))
      : h("p", { class: "text-muted mb-0", text: "No one has registered yet." }));
  } catch (err) {
    $("#participants").replaceChildren(errorBox(err.message, loadPanel));
  }
}

async function checkIn(token) {
  const result = $("#scan-result");
  try {
    const r = await api(`/events/${selectedId}/check-in`, { method: "POST", body: { token } });
    result.replaceChildren(h("div", { class: `alert ${r.result === "already" ? "alert-warning" : "alert-success"} mb-0` },
      h("strong", { text: r.result === "already" ? "Already checked in. " : "Checked in. " }), `${r.name} (${r.reg_no})`));
    loadPanel();
  } catch (err) {
    result.replaceChildren(h("div", { class: "alert alert-danger mb-0" }, h("strong", { text: "Not accepted. " }), err.message));
  }
}

$("#token-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const value = $("#token-input").value.trim();
  if (value.length < 10) {
    showMessage($("#scan-result"), "Enter the full ticket code.", "warning");
    return;
  }
  checkIn(value);
  $("#token-input").value = "";
});

$("#scan-toggle").addEventListener("click", async (e) => {
  const button = e.currentTarget;
  if (scanner) {
    await scanner.stop().catch(() => {});
    scanner = null;
    button.textContent = "Start camera";
    return;
  }
  try {
    scanner = new Html5Qrcode("reader");
    await scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: 220 }, (text) => {
      const now = Date.now();
      if (text === lastScan.token && now - lastScan.at < 3000) return; // ignore the same code held in view
      lastScan = { token: text, at: now };
      checkIn(text);
    });
    button.textContent = "Stop camera";
  } catch {
    scanner = null;
    showMessage($("#scan-result"), "The camera could not be started. Allow camera access, or enter the ticket code instead.", "warning");
  }
});

$("#tab-checkin").addEventListener("hide.bs.tab", () => { if (scanner) $("#scan-toggle").click(); });

/* ---------- Create / edit form ---------- */
function renderPreview() {
  $("#poster-preview").replaceChildren(poster({
    title: $("#f-title").value || "Event title",
    poster_style: $("#f-style").value,
    starts_at: $("#f-start").value ? toIstIso($("#f-start").value) : new Date().toISOString(),
    club: clubs.find((c) => c.id === clubId),
  }));
}

function openForm(event) {
  editing = event;
  form.reset();
  form.classList.remove("was-validated");
  $("#event-msg").replaceChildren();
  $("#event-modal-title").textContent = event ? "Edit event" : "New event";
  $("#event-submit").textContent = event ? "Save changes" : "Publish event";
  const locked = Boolean(event && (event.confirmed + event.waitlisted) > 0);
  ["#f-start", "#f-end", "#f-deadline"].forEach((id) => { $(id).disabled = locked; });
  $("#time-lock").hidden = !locked;

  if (event) {
    $("#f-title").value = event.title;
    $("#f-category").value = event.category;
    $("#f-venue").value = event.venue;
    $("#f-capacity").value = event.capacity;
    $("#f-capacity").min = Math.max(1, event.confirmed);
    $("#f-start").value = toLocalInput(event.starts_at);
    $("#f-end").value = toLocalInput(event.ends_at);
    $("#f-deadline").value = toLocalInput(event.registration_deadline);
    $("#f-desc").value = event.description;
    $("#f-style").value = event.poster_style;
  } else {
    $("#f-category").value = clubs.find((c) => c.id === clubId)?.category || "Other";
    $("#f-capacity").min = 1;
  }
  renderPreview();
  eventModal.show();
}

function validateDates() {
  const start = $("#f-start"), end = $("#f-end"), deadline = $("#f-deadline");
  if (start.disabled) return;
  const now = toLocalInput(new Date().toISOString());
  start.setCustomValidity(start.value && start.value <= now ? "past" : "");
  end.setCustomValidity(end.value && start.value && end.value <= start.value ? "order" : "");
  deadline.setCustomValidity(deadline.value && start.value && deadline.value > start.value ? "order" : "");
}

["#f-title", "#f-style", "#f-start"].forEach((id) => $(id).addEventListener("input", renderPreview));
$("#f-start").addEventListener("change", () => {
  if ($("#f-start").value && !$("#f-deadline").value) $("#f-deadline").value = $("#f-start").value;
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  validateDates();
  form.classList.add("was-validated");
  if (!form.checkValidity()) return;
  const body = {
    club_id: clubId,
    title: $("#f-title").value,
    category: $("#f-category").value,
    venue: $("#f-venue").value,
    capacity: Number($("#f-capacity").value),
    starts_at: toIstIso($("#f-start").value),
    ends_at: toIstIso($("#f-end").value),
    registration_deadline: toIstIso($("#f-deadline").value),
    description: $("#f-desc").value,
    poster_style: $("#f-style").value,
  };
  try {
    await withBusy($("#event-submit"), () => editing
      ? api(`/events/${editing.id}`, { method: "PUT", body })
      : api("/events", { method: "POST", body }), "Saving…");
    eventModal.hide();
    toast(editing ? "Event updated." : "Event published.");
    loadEvents();
  } catch (err) {
    showMessage($("#event-msg"), err.message);
  }
});

$("#new-event").addEventListener("click", () => openForm(null));

/* ---------- Club selection ---------- */
function chooseClub(id) {
  clubId = id;
  const club = clubs.find((c) => c.id === id);
  $("#club-heading").textContent = club.name;
  $("#club-select").value = String(id);
  loadEvents();
}

$("#club-select").addEventListener("change", (e) => {
  selectedId = null;
  $("#event-panel").hidden = true;
  history.replaceState(null, "", `?club=${e.target.value}`);
  chooseClub(Number(e.target.value));
});

initPage("organizer").then(async (user) => {
  if (!requireLogin()) return;
  try {
    clubs = await api("/organizer/clubs");
  } catch (err) {
    $("#event-table").replaceChildren(errorBox(err.message));
    return;
  }
  if (!clubs.length) {
    $("#main").replaceChildren(emptyState("You do not manage an approved club yet.",
      h("a", { class: "btn btn-sm btn-primary", href: "register-club.html", text: "Register a club" })));
    return;
  }
  clubs.forEach((c) => $("#club-select").append(h("option", { value: c.id, text: c.name })));
  $("#club-picker").hidden = clubs.length < 2;
  const wanted = Number(param("club"));
  selectedId = Number(param("event")) || null;
  chooseClub(clubs.some((c) => c.id === wanted) ? wanted : clubs[0].id);
});
