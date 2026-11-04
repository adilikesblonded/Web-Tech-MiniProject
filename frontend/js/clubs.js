const categorySelect = $("#club-category");
CATEGORIES.forEach((c) => categorySelect.append(h("option", { value: c, text: c })));

async function loadClubs() {
  const list = $("#club-list");
  list.replaceChildren(loading("Loading clubs…"));
  const query = new URLSearchParams();
  const q = $("#club-search").value.trim();
  if (q) query.set("q", q);
  if (categorySelect.value) query.set("category", categorySelect.value);
  try {
    const clubs = await api(`/clubs?${query}`);
    if (!clubs.length) {
      list.replaceChildren(emptyState("No clubs match your search.",
        h("button", { class: "btn btn-sm btn-outline-dark", type: "button", text: "Clear search",
          onclick: () => { $("#club-search").value = ""; categorySelect.value = ""; loadClubs(); } })));
      return;
    }
    list.replaceChildren(h("ul", { class: "list-unstyled border-top" }, clubs.map((c) =>
      h("li", {},
        h("a", { class: "club-row", href: `club.html?id=${c.id}` },
          monogram(c),
          h("div", { class: "flex-grow-1" },
            h("h3", { text: c.name }),
            h("p", { class: "meta mb-1", text: c.category }),
            h("p", { class: "mb-0", text: c.description })),
          h("span", { class: "meta small text-nowrap d-none d-sm-inline",
            text: c.upcoming_events ? `${c.upcoming_events} upcoming` : "No upcoming events" }))))));
  } catch (err) {
    list.replaceChildren(errorBox(err.message, loadClubs));
  }
}

$("#club-filters").addEventListener("submit", (e) => { e.preventDefault(); loadClubs(); });
categorySelect.addEventListener("change", loadClubs);

initPage("clubs").then(loadClubs);
