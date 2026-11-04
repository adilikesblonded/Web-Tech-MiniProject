/* Shared helpers used by every page: API calls, header/footer, formatting, small DOM builders. */

const TZ = "Asia/Kolkata";
const CATEGORIES = ["Music", "Theatre", "Dance", "Photography", "Literary", "Technology", "Other"];

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function api(path, { method = "GET", body } = {}) {
  const options = { method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new ApiError("Could not reach the server. Check your connection and try again.", 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
    throw new ApiError(detail, response.status, data);
  }
  return data;
}

/* Build elements safely: text always goes through textContent. */
function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

const $ = (selector, root = document) => root.querySelector(selector);
const param = (name) => new URLSearchParams(location.search).get(name);

/* Dates are always shown in IST. */
function fmt(iso, options) {
  return new Intl.DateTimeFormat("en-IN", { timeZone: TZ, ...options }).format(new Date(iso));
}
const fmtDate = (iso) => fmt(iso, { weekday: "short", day: "numeric", month: "short" });
const fmtTime = (iso) => fmt(iso, { hour: "numeric", minute: "2-digit" });
const fmtDateTime = (iso) => `${fmtDate(iso)}, ${fmtTime(iso)}`;
const fmtMonth = (iso) => fmt(iso, { month: "short" });
const fmtDay = (iso) => fmt(iso, { day: "numeric" });
const fmtRange = (start, end) => `${fmtDate(start)} · ${fmtTime(start)} – ${fmtTime(end)} IST`;

/* <input type="datetime-local"> values are treated as IST. */
function toIstIso(localValue) {
  return `${localValue}:00+05:30`;
}
function toLocalInput(iso) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(new Date(iso)).map((p) => [p.type, p.value])
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

/* Status label with text, never colour alone. */
function statusLabel(text) {
  const t = text.toLowerCase();
  let kind = "open";
  if (t.includes("cancel")) kind = "cancelled";
  else if (t.includes("reject")) kind = "rejected";
  else if (t.includes("full")) kind = "full";
  else if (t.includes("left")) kind = "few";
  else if (t.includes("wait")) kind = "waitlisted";
  else if (t.includes("pending")) kind = "pending";
  else if (t.includes("closed")) kind = "closed";
  else if (t.includes("checked") || t.includes("attended")) kind = "checked";
  else if (t.includes("ended") || t.includes("past") || t.includes("missed")) kind = "ended";
  return h("span", { class: `status status-${kind}`, text });
}

function poster(event, large = false) {
  return h("div", { class: `poster poster--${event.poster_style}${large ? " poster-lg" : ""}`, "aria-hidden": "true" },
    h("span", { class: "p-club", text: event.club.short_name }),
    h("p", { class: "p-title", text: event.title }),
    h("span", { class: "p-date", text: `${fmtDate(event.starts_at)} · ${fmtTime(event.starts_at)}` })
  );
}

function eventCard(event) {
  return h("a", { class: "event-card", href: `event.html?id=${event.id}` },
    poster(event),
    h("div", { class: "card-body" },
      h("span", { class: "event-date", text: `${fmtDate(event.starts_at)} · ${fmtTime(event.starts_at)}` }),
      h("h3", { text: event.title }),
      h("span", { class: "meta", text: `${event.club.short_name} · ${event.venue}` }),
      h("div", { class: "mt-auto pt-2 d-flex gap-2 align-items-center" },
        statusLabel(event.availability),
        h("span", { class: "meta small", text: event.category })
      )
    )
  );
}

function monogram(club, large = false) {
  const letters = club.short_name.replace(/[^A-Za-z0-9 &]/g, "").split(/\s+/).filter(Boolean)
    .map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return h("span", { class: `monogram mono-${club.category}${large ? " monogram-lg" : ""}`, "aria-hidden": "true", text: letters });
}

function emptyState(message, action) {
  return h("div", { class: "empty-state" }, h("p", { class: "mb-2", text: message }), action || null);
}

function loading(text = "Loading…") {
  return h("div", { class: "d-flex align-items-center gap-2 text-muted py-4", role: "status" },
    h("span", { class: "spinner-border spinner-border-sm", "aria-hidden": "true" }), text);
}

function errorBox(message, retry) {
  return h("div", { class: "alert alert-danger d-flex justify-content-between align-items-center gap-3", role: "alert" },
    h("span", { text: message }),
    retry ? h("button", { class: "btn btn-sm btn-outline-danger", type: "button", onclick: retry, text: "Try again" }) : null
  );
}

/* Inline form message inside an aria-live region. */
function showMessage(container, message, type = "danger") {
  container.replaceChildren(h("div", { class: `alert alert-${type} py-2 mb-0`, text: message }));
}

function toast(message, type = "success") {
  let holder = $("#toast-holder");
  if (!holder) {
    holder = h("div", { id: "toast-holder", class: "toast-container position-fixed bottom-0 end-0 p-3", "aria-live": "polite" });
    document.body.append(holder);
  }
  const node = h("div", { class: `toast align-items-center text-bg-${type} border-0`, role: "status" },
    h("div", { class: "d-flex" },
      h("div", { class: "toast-body", text: message }),
      h("button", { type: "button", class: "btn-close btn-close-white me-2 m-auto", "data-bs-dismiss": "toast", "aria-label": "Close" })
    )
  );
  holder.append(node);
  const t = new bootstrap.Toast(node, { delay: 3500 });
  node.addEventListener("hidden.bs.toast", () => node.remove());
  t.show();
}

/* Disable a button while a request runs. */
async function withBusy(button, task, busyText = "Please wait…") {
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = busyText;
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.innerHTML = original;
  }
}

/* ---------- Session and layout ---------- */
let currentUser = null;

async function loadUser() {
  try {
    currentUser = (await api("/auth/me")).user;
  } catch {
    currentUser = null;
  }
  return currentUser;
}

function requireLogin() {
  if (!currentUser) {
    location.href = `login.html?next=${encodeURIComponent(location.pathname.slice(1) + location.search)}`;
    return false;
  }
  return true;
}

function renderHeader(active) {
  const link = (href, label, key) =>
    h("li", { class: "nav-item" },
      h("a", { class: `nav-link${active === key ? " active" : ""}`, href, "aria-current": active === key ? "page" : null, text: label }));

  const items = [link("index.html", "Explore", "explore"), link("clubs.html", "Clubs", "clubs")];
  if (currentUser) items.push(link("my-events.html", "My events", "my"));
  if (currentUser?.is_organizer) items.push(link("organizer.html", "Manage events", "organizer"));
  if (currentUser?.is_admin) items.push(link("admin.html", "Review clubs", "admin"));

  const account = currentUser
    ? h("div", { class: "d-flex align-items-center gap-2 mt-2 mt-lg-0" },
        h("span", { class: "small text-muted d-none d-lg-inline", text: currentUser.name }),
        h("button", { class: "btn btn-sm btn-outline-dark", type: "button", text: "Log out", onclick: logout }))
    : h("div", { class: "d-flex gap-2 mt-2 mt-lg-0" },
        h("a", { class: "btn btn-sm btn-outline-dark", href: "login.html", text: "Log in" }),
        h("a", { class: "btn btn-sm btn-primary", href: "login.html#signup", text: "Sign up" }));

  const header = $("#site-header");
  header.className = "site-header";
  header.replaceChildren(
    h("nav", { class: "navbar navbar-expand-lg", "aria-label": "Main" },
      h("div", { class: "container" },
        h("a", { class: "navbar-brand d-flex flex-column lh-1", href: "index.html" },
          h("span", {}, "Event", h("span", { text: "ify" })),
          h("small", { class: "brand-tag fw-normal mt-1", text: "MIT after class" })),
        h("button", {
          class: "navbar-toggler", type: "button", "data-bs-toggle": "collapse", "data-bs-target": "#main-nav",
          "aria-controls": "main-nav", "aria-expanded": "false", "aria-label": "Toggle navigation",
        }, h("span", { class: "navbar-toggler-icon" })),
        h("div", { class: "collapse navbar-collapse", id: "main-nav" },
          h("ul", { class: "navbar-nav mx-lg-4 me-auto" }, items),
          account)
      )
    )
  );
}

function renderFooter() {
  const footer = $("#site-footer");
  footer.className = "site-footer mt-5";
  footer.replaceChildren(
    h("div", { class: "container py-4 d-flex flex-column flex-md-row justify-content-between gap-2" },
      h("span", { text: `© ${new Date().getFullYear()} Eventify · Campus events at MIT Manipal` }),
      h("span", { text: "A student project. Not affiliated with MIT Manipal or the clubs listed." })
    )
  );
}

async function logout() {
  try { await api("/auth/logout", { method: "POST" }); } catch { /* signed out locally anyway */ }
  location.href = "index.html";
}

async function initPage(active) {
  await loadUser();
  renderHeader(active);
  renderFooter();
  return currentUser;
}
