const filters = { q: "", category: "", from: "", to: "" };

function renderFeatured(events) {
  const holder = $("#featured");
  const open = events.filter((e) => e.phase === "upcoming");
  if (!open.length) {
    $("#featured-section").hidden = true;
    return;
  }
  const featured = open.find((e) => e.seats_left > 0) || open[0];
  const next = open.filter((e) => e.id !== featured.id).slice(0, 4);

  holder.replaceChildren(
    h("div", { class: "col-lg-7" },
      h("a", { href: `event.html?id=${featured.id}`, class: "d-block text-decoration-none" }, poster(featured, true)),
      h("div", { class: "d-flex flex-wrap justify-content-between align-items-end gap-2 mt-3" },
        h("div", {},
          h("p", { class: "eyebrow mb-1", text: "Featured" }),
          h("h3", { class: "h4 mb-1" }, h("a", { href: `event.html?id=${featured.id}`, class: "link-dark text-decoration-none", text: featured.title })),
          h("p", { class: "meta mb-0", text: `${featured.club.name} · ${fmtRange(featured.starts_at, featured.ends_at)}` })),
        statusLabel(featured.availability))
    ),
    h("div", { class: "col-lg-5" },
      h("div", { class: "surface p-4 h-100" },
        h("h3", { class: "h5 mb-2 display-serif", text: "Coming up" }),
        next.length
          ? h("ul", { class: "list-unstyled mb-0 coming-up" }, next.map((e) =>
              h("li", {},
                h("a", { href: `event.html?id=${e.id}` },
                  h("span", { class: "date-chip" },
                    h("span", { class: "m d-block", text: fmtMonth(e.starts_at) }),
                    h("span", { class: "d d-block", text: fmtDay(e.starts_at) })),
                  h("span", {},
                    h("span", { class: "cu-title d-block fw-semibold", text: e.title }),
                    h("span", { class: "meta d-block", text: `${e.club.short_name} · ${fmtTime(e.starts_at)} · ${e.venue}` }))))))
          : h("p", { class: "text-muted mb-0", text: "More events will appear here soon." })
      )
    )
  );
}

function renderCategoryChips() {
  const holder = $("#category-filters");
  const chip = (value, label) =>
    h("button", {
      type: "button", class: "btn btn-outline-dark", "aria-pressed": String(filters.category === value), text: label,
      onclick: () => { filters.category = value; renderCategoryChips(); loadGrid(); },
    });
  holder.replaceChildren(chip("", "All"), ...CATEGORIES.filter((c) => c !== "Other").map((c) => chip(c, c)));
}

function hasFilters() {
  return filters.q || filters.category || filters.from || filters.to;
}

function clearFilters() {
  Object.assign(filters, { q: "", category: "", from: "", to: "" });
  $("#search").value = $("#from-date").value = $("#to-date").value = "";
  renderCategoryChips();
  loadGrid();
}

async function loadGrid() {
  const grid = $("#event-grid");
  grid.replaceChildren(loading("Loading events…"));
  const query = new URLSearchParams();
  if (filters.q) query.set("q", filters.q);
  if (filters.category) query.set("category", filters.category);
  if (filters.from) query.set("from_date", filters.from);
  if (filters.to) query.set("to_date", filters.to);
  try {
    const events = await api(`/events?${query}`);
    $("#result-count").textContent = `${events.length} event${events.length === 1 ? "" : "s"}`;
    if (!events.length) {
      grid.replaceChildren(h("div", { class: "col-12" },
        emptyState(hasFilters() ? "No events match these filters." : "There are no upcoming events right now.",
          hasFilters() ? h("button", { class: "btn btn-sm btn-outline-dark", type: "button", text: "Clear filters", onclick: clearFilters }) : null)));
      return;
    }
    grid.replaceChildren(...events.map((e) => h("div", { class: "col-12 col-md-6 col-lg-4" }, eventCard(e))));
  } catch (err) {
    grid.replaceChildren(h("div", { class: "col-12" }, errorBox(err.message, loadGrid)));
  }
}

async function loadFeatured() {
  try {
    renderFeatured(await api("/events"));
  } catch {
    $("#featured-section").hidden = true;
  }
}

$("#search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  filters.q = $("#search").value.trim();
  loadGrid();
  $("#all-title").scrollIntoView({ behavior: "smooth", block: "start" });
});
$("#from-date").addEventListener("change", (e) => { filters.from = e.target.value; loadGrid(); });
$("#to-date").addEventListener("change", (e) => { filters.to = e.target.value; loadGrid(); });

initPage("explore").then(() => {
  renderCategoryChips();
  loadFeatured();
  loadGrid();
});
