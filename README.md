# Eventify — MIT after class

A campus event platform for MIT Manipal clubs. Students find events, reserve a seat or join a waitlist, and show a QR ticket at the door. Club organizers publish events and check attendees in. An administrator approves new clubs.

**Web Technology project (ICT3131), V Semester BTech.**

## Tech stack

| Layer | Technology |
| --- | --- |
| Front end | HTML5, CSS3, vanilla JavaScript (`fetch` + JSON) |
| CSS framework | Bootstrap 5.3.3 (bundled locally in `frontend/vendor/`) |
| QR scanning | html5-qrcode 2.3.8 (bundled locally) |
| Back end | Python 3.11+, FastAPI, Pydantic |
| Database | PostgreSQL 14+ via SQLAlchemy 2 and psycopg 3 |
| QR generation | `qrcode` (SVG, server side) |

## Features

| # | Feature | Owner |
| --- | --- | --- |
| 1 | Accounts: sign up, log in, log out (hashed passwords, HttpOnly session cookie) | Member 1 |
| 2 | Club registration and admin approval (pending → approved / rejected with reason) | Member 1 |
| 3 | Event management for organizers: create, edit, cancel, poster style picker | Member 1 |
| 4 | Explore events: search, category and date filters, club directory and club pages | Member 2 |
| 5 | Registration with seat limits and a first-come waitlist with automatic promotion | Member 2 |
| 6 | QR tickets, organizer check-in (camera or ticket code) and attendance dashboard | Member 2 |

## Setup

1. Install Python 3.11+ and PostgreSQL, then create a database:

   ```bash
   createdb eventify
   ```

2. Install dependencies (a virtual environment is recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Point the app at your database. Copy `.env.example` to `.env` and edit it, or export the variable directly:

   ```bash
   export DATABASE_URL="postgresql+psycopg://postgres:yourpassword@localhost:5432/eventify"
   # Windows PowerShell: $env:DATABASE_URL="postgresql+psycopg://postgres:yourpassword@localhost:5432/eventify"
   ```

4. Load the demo data (this resets all tables), then start the server from the project root:

   ```bash
   python -m backend.seed
   uvicorn backend.main:app --reload
   ```

5. Open http://localhost:8000. API docs are at http://localhost:8000/docs.

Re-run `python -m backend.seed` shortly before a demo. Event dates are set relative to when the seed runs, and "Build Your First Web App" starts 20 minutes later so check-in can be shown straight away (check-in opens 30 minutes before an event starts).

## Demo accounts

Every password is `demo1234` except the admin's.

| Role | Email |
| --- | --- |
| Administrator (also organizer of The Photography Club and IECSE) | `admin@example.com` (password `admin1234`) |
| Students | `student1@example.com` … `student6@example.com` |
| Organizers | `chords.organizer`, `aaina.organizer`, `blitzkrieg.organizer`, `ldq.organizer`, `mist.organizer`, `ieee.organizer` (all `@example.com`) |

## Suggested demo (about 5 minutes)

Everything below uses the one admin account.

1. **Accounts:** log in as `admin@example.com`. Log out at the end of the demo.
2. **Explore events:** on Explore, search and use the category and date filters. Open Clubs and a club page.
3. **Club approval:** Register a club, then open Review clubs. Approve your application and reject *Campus Board Games Society* with a reason.
4. **Event management:** Manage events → pick your new club. Create an event with a poster style, edit it, then cancel it.
5. **Seat limits and waitlist:** register for *After Class: Open Mic*. Open *Circuits & Coffee* (full) and join the waitlist.
6. **Automatic promotion:** My events shows you at #2 for *Frame by Frame: Campus Photo Walk*. Manage events → The Photography Club → edit the event and raise capacity to 3: Student 5 is promoted first and you move to #1. Raise it to 4: you are promoted and get a ticket.
7. **QR ticket and check-in:** My events → Show ticket for *Build Your First Web App* and copy the ticket code. Manage events → IECSE → Manage → Check-in, then paste the code (or scan the QR from a second screen). Submit it again to show "Already checked in". The totals update.

## How it works

- The front end is plain HTML pages. Each page's JavaScript calls JSON routes under `/api` with `fetch()` and builds the page with `textContent` (never raw HTML), so user text cannot inject markup.
- FastAPI validates every request with Pydantic schemas (server-side validation). Forms also use HTML5 constraints and Bootstrap validation styles (client-side validation).
- Permissions are checked on the server: organizers can only touch events of clubs they own, and only the admin can review clubs.
- Registration locks the event row (`SELECT … FOR UPDATE`) inside a transaction, so two students cannot take the last seat at the same time. A unique `(event_id, user_id)` constraint stops duplicate registrations.
- Check-in uses a conditional `UPDATE … WHERE checked_in_at IS NULL`, so scanning a ticket twice only counts once.
- Seat counts, waitlist positions and attendance are always calculated from the `registrations` table, never stored as counters.

## Project structure

```
backend/
  main.py            app setup, error handling, serves the frontend
  database.py        database connection
  models.py          tables: users, sessions, clubs, events, registrations
  schemas.py         request validation
  security.py        password hashing, sessions, permission checks
  services.py        seat counting, waitlist promotion, JSON helpers
  seed.py            demo data
  routers/           auth, clubs (+ admin), events, registrations (+ check-in)
frontend/
  *.html             index, event, clubs, club, login, my-events,
                     register-club, organizer, admin
  css/styles.css     shared theme and responsive rules
  js/app.js          shared API helper, header/footer, formatting
  js/*.js            page scripts
  vendor/            Bootstrap and html5-qrcode
```

## Notes

- The camera scanner needs `localhost` or HTTPS. On another device over plain HTTP, use the ticket code box instead.
- Club names are real MIT Manipal clubs; every event, venue and account is sample data. This is a student project and is not affiliated with MIT Manipal or the clubs.
