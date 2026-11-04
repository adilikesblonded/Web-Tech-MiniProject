const eventId = Number(param("id"));

function bookingActions(event) {
  const mine = event.my_registration;
  const msg = h("div", { "aria-live": "polite", class: "mt-2" });
  const closed = new Date() > new Date(event.registration_deadline);

  async function send(joinWaitlist, button) {
    msg.replaceChildren();
    try {
      const result = await withBusy(button, () =>
        api(`/events/${event.id}/registrations`, { method: "POST", body: { join_waitlist: joinWaitlist } }));
      toast(result.status === "confirmed" ? "Seat confirmed. Your ticket is in My events." : `You are #${result.position} on the waitlist.`);
      load();
    } catch (err) {
      if (err.body?.code === "full") {
        showMessage(msg, "The last seat was just taken. You can join the waitlist instead.", "warning");
        load();
      } else {
        showMessage(msg, err.message);
      }
    }
  }

  async function cancel(button) {
    const text = mine.status === "waitlisted" ? "Leave the waitlist for this event?" : "Cancel your seat? It may go to someone on the waitlist.";
    if (!confirm(text)) return;
    try {
      await withBusy(button, () => api(`/events/${event.id}/registrations/me`, { method: "DELETE" }));
      toast(mine.status === "waitlisted" ? "You have left the waitlist." : "Your registration was cancelled.");
      load();
    } catch (err) {
      showMessage(msg, err.message);
    }
  }

  if (event.is_owner) {
    return h("div", {},
      h("a", { class: "btn btn-success w-100", href: `organizer.html?club=${event.club.id}&event=${event.id}`, text: "Manage this event" }),
      h("p", { class: "small text-muted mt-2 mb-0", text: "You organise this event." }));
  }
  if (event.status === "cancelled") {
    return h("p", { class: "mb-0", text: "This event has been cancelled by the organisers." });
  }
  if (mine?.status === "confirmed") {
    const started = new Date() >= new Date(event.starts_at);
    return h("div", {},
      h("p", { class: "mb-2" }, statusLabel(mine.checked_in ? "Checked in" : "Confirmed")),
      h("a", { class: "btn btn-primary w-100", href: "my-events.html", text: "View my ticket" }),
      !started && !mine.checked_in
        ? h("button", { class: "btn btn-link link-danger w-100 mt-1", type: "button", text: "Cancel registration", onclick: (e) => cancel(e.currentTarget) })
        : null,
      msg);
  }
  if (mine?.status === "waitlisted") {
    return h("div", {},
      h("p", { class: "mb-1" }, statusLabel(closed ? "Registration closed" : "Waitlisted")),
      h("p", { class: "small text-muted", text: closed ? "Registration closed before a seat opened up." : `You are #${mine.position} in the queue. If a seat opens up, it is confirmed automatically.` }),
      !closed ? h("button", { class: "btn btn-outline-dark w-100", type: "button", text: "Leave waitlist", onclick: (e) => cancel(e.currentTarget) }) : null,
      msg);
  }
  if (event.phase !== "upcoming" || closed) {
    return h("button", { class: "btn btn-secondary w-100", type: "button", disabled: true, text: "Registration closed" });
  }
  if (!currentUser) {
    return h("a", { class: "btn btn-primary w-100", href: `login.html?next=${encodeURIComponent(`event.html?id=${event.id}`)}`, text: "Log in to register" });
  }
  if (event.seats_left > 0) {
    return h("div", {}, h("button", { class: "btn btn-primary w-100", type: "button", text: "Register", onclick: (e) => send(false, e.currentTarget) }), msg);
  }
  return h("div", {},
    h("button", { class: "btn btn-primary w-100", type: "button", text: "Join waitlist", onclick: (e) => send(true, e.currentTarget) }),
    h("p", { class: "small text-muted mt-2 mb-0", text: `${event.waitlisted} already waiting. Seats go to the waitlist in order.` }),
    msg);
}

function render(event) {
  document.title = `${event.title} · Eventify`;
  const pct = Math.min(100, Math.round((event.confirmed / event.capacity) * 100));
  $("#event-view").replaceChildren(
    h("nav", { "aria-label": "Breadcrumb", class: "mb-3" },
      h("ol", { class: "breadcrumb small" },
        h("li", { class: "breadcrumb-item" }, h("a", { href: "index.html", text: "Explore" })),
        h("li", { class: "breadcrumb-item active", "aria-current": "page", text: event.title }))),
    h("div", { class: "row gy-3 gx-lg-5" },
      h("div", { class: "col-lg-8 order-1" },
        h("p", { class: "eyebrow mb-2", text: event.category }),
        h("h1", { class: "mb-2", text: event.title }),
        h("p", { class: "meta mb-0" }, "Hosted by ", h("a", { href: `club.html?id=${event.club.id}`, text: event.club.name }))
      ),
      h("div", { class: "col-lg-8 order-3 order-lg-2" },
        poster(event, true),
        h("h2", { class: "h4 mt-4", text: "About this event" }),
        h("p", { class: "description", text: event.description })
      ),
      h("aside", { class: "col-lg-4 order-2 order-lg-3", "aria-label": "Booking" },
        h("div", { class: "surface p-4 booking-panel" },
          h("div", { class: "d-flex justify-content-between align-items-center mb-3" },
            h("h2", { class: "h5 mb-0 display-serif", text: "Details" }), statusLabel(event.availability)),
          h("dl", { class: "info-list mb-2" },
            h("dt", { text: "When" }), h("dd", { text: fmtRange(event.starts_at, event.ends_at) }),
            h("dt", { text: "Where" }), h("dd", { text: event.venue }),
            h("dt", { text: "Registration closes" }), h("dd", { text: `${fmtDateTime(event.registration_deadline)} IST` }),
            h("dt", { text: "Seats" }),
            h("dd", {},
              h("span", { text: `${event.confirmed} of ${event.capacity} taken` }),
              h("div", { class: "progress seat-bar mt-2", role: "progressbar", "aria-label": "Seats taken",
                "aria-valuenow": String(pct), "aria-valuemin": "0", "aria-valuemax": "100" },
                h("div", { class: "progress-bar", style: `width:${pct}%` })))
          ),
          bookingActions(event)
        )
      )
    )
  );
}

async function load() {
  const view = $("#event-view");
  if (!view.children.length) view.replaceChildren(loading("Loading event…"));
  try {
    render(await api(`/events/${eventId}`));
  } catch (err) {
    view.replaceChildren(err.status === 404
      ? emptyState("This event could not be found.", h("a", { class: "btn btn-sm btn-outline-dark", href: "index.html", text: "Browse events" }))
      : errorBox(err.message, load));
  }
}

initPage("explore").then(load);
