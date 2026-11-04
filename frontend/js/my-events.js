const ticketModal = new bootstrap.Modal($("#ticket-modal"));

async function showTicket(reg) {
  const body = $("#ticket-body");
  body.replaceChildren(loading("Loading ticket…"));
  ticketModal.show();
  try {
    const t = await api(`/registrations/${reg.id}/ticket`);
    body.replaceChildren(
      h("p", { class: "fw-semibold mb-1", text: t.event_title }),
      h("p", { class: "meta mb-3", text: `${fmtRange(reg.event.starts_at, reg.event.ends_at)} · ${reg.event.venue}` }),
      h("img", { class: "ticket-qr mx-auto d-block", src: `/api/registrations/${reg.id}/qr.svg`,
        alt: `QR code ticket for ${t.event_title}` }),
      h("p", { class: "mt-3 mb-1 fw-semibold", text: `${t.name} · ${t.reg_no}` }),
      t.checked_in ? statusLabel("Checked in") : h("p", { class: "small text-muted mb-1", text: "Show this code at the entrance." }),
      h("p", { class: "small text-muted mb-0 mt-2" }, "Ticket code: ", h("span", { class: "token-text", text: t.token }))
    );
  } catch (err) {
    body.replaceChildren(errorBox(err.message));
  }
}

async function cancelReg(reg, button) {
  const text = reg.status === "waitlisted" ? `Leave the waitlist for ${reg.event.title}?` : `Cancel your seat for ${reg.event.title}?`;
  if (!confirm(text)) return;
  try {
    await withBusy(button, () => api(`/events/${reg.event.id}/registrations/me`, { method: "DELETE" }));
    toast("Registration cancelled.");
    load();
  } catch (err) {
    toast(err.message, "danger");
  }
}

function row(reg, actions) {
  const e = reg.event;
  return h("li", { class: "surface p-3 mb-3" },
    h("div", { class: "d-flex flex-column flex-md-row gap-3 align-items-md-center" },
      h("span", { class: "date-chip" },
        h("span", { class: "m d-block", text: fmtMonth(e.starts_at) }),
        h("span", { class: "d d-block", text: fmtDay(e.starts_at) })),
      h("div", { class: "flex-grow-1" },
        h("a", { href: `event.html?id=${e.id}`, class: "fw-semibold link-dark", text: e.title }),
        h("p", { class: "meta mb-0", text: `${e.club.short_name} · ${fmtTime(e.starts_at)} · ${e.venue}` })),
      h("div", { class: "d-flex flex-wrap gap-2 align-items-center" }, actions)));
}

function render(regs) {
  const upcoming = regs.filter((r) => r.event.phase !== "past");
  const tickets = upcoming.filter((r) => r.status === "confirmed");
  const waiting = upcoming.filter((r) => r.status === "waitlisted");
  const past = regs.filter((r) => r.event.phase === "past" && r.status === "confirmed").reverse();

  $("#tickets").replaceChildren(tickets.length
    ? h("ul", { class: "list-unstyled mb-0" }, tickets.map((r) => {
        const cancelled = r.event.status === "cancelled";
        const started = new Date() >= new Date(r.event.starts_at);
        return row(r, cancelled
          ? [statusLabel("Event cancelled")]
          : [
              statusLabel(r.checked_in_at ? "Checked in" : "Confirmed"),
              h("button", { class: "btn btn-sm btn-primary", type: "button", text: "Show ticket", onclick: () => showTicket(r) }),
              !started && !r.checked_in_at
                ? h("button", { class: "btn btn-sm btn-outline-dark", type: "button", text: "Cancel", onclick: (ev) => cancelReg(r, ev.currentTarget) })
                : null,
            ]);
      }))
    : emptyState("You have no upcoming tickets.", h("a", { class: "btn btn-sm btn-primary", href: "index.html", text: "Find an event" })));

  $("#waitlist").replaceChildren(waiting.length
    ? h("ul", { class: "list-unstyled mb-0" }, waiting.map((r) => row(r,
        r.waitlist_closed
          ? [statusLabel("Registration closed"), h("span", { class: "small text-muted", text: "No seat confirmed" })]
          : [statusLabel(`Waitlisted · #${r.position}`),
             h("button", { class: "btn btn-sm btn-outline-dark", type: "button", text: "Leave waitlist", onclick: (ev) => cancelReg(r, ev.currentTarget) })])))
    : h("p", { class: "text-muted", text: "You are not on any waitlists." }));

  $("#past").replaceChildren(past.length
    ? h("ul", { class: "list-unstyled mb-0" }, past.map((r) => row(r, [statusLabel(r.checked_in_at ? "Attended" : "Missed")])))
    : h("p", { class: "text-muted", text: "Events you attend will show up here." }));
}

async function load() {
  try {
    render(await api("/me/registrations"));
  } catch (err) {
    $("#tickets").replaceChildren(errorBox(err.message, load));
  }
}

initPage("my").then((user) => {
  if (!requireLogin()) return;
  $("#tickets").replaceChildren(loading());
  load();
});
