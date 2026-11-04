"""Reset the database and load demo data. Run from the project root: python -m backend.seed"""
from datetime import datetime, time, timedelta, timezone

from .database import Base, SessionLocal, engine
from .models import Club, Event, Registration, User
from .security import hash_password, new_ticket_token

IST = timezone(timedelta(hours=5, minutes=30))
PASSWORD = "demo1234"
ADMIN_CLUBS = ("photography", "iecse")  # owned by the admin so one account can show every feature

CLUBS = [
    ("Chords and Co.", "Chords & Co.", "Music", "chords",
     "A music community for students who like to play, sing and perform, from jam sessions to stage nights."),
    ("Aaina Dramatics", "Aaina", "Theatre", "aaina",
     "The dramatics club of MIT, covering acting, scripting, direction and everything that goes into a performance."),
    ("Blitzkrieg Dance Crew India", "Blitzkrieg", "Dance", "blitzkrieg",
     "A dance crew focused on performance, choreography and dance culture across styles."),
    ("The Photography Club", "Photography Club", "Photography", "photography",
     "A club for students who enjoy photography, photo walks and learning to tell stories with a camera."),
    ("Literary, Debate and Quiz Club", "LDQ", "Literary", "ldq",
     "A home for readers, writers, debaters and quizzers, with regular quizzes and debates on campus."),
    ("IECSE Manipal", "IECSE", "Technology", "iecse",
     "The computer science and IT student club at MIT, known for development workshops and coding competitions."),
    ("Manipal Information Security Team", "MIST", "Technology", "mist",
     "A student team focused on information and network security, with hands-on security challenges."),
    ("IEEE Student Branch Manipal", "IEEE SBM", "Technology", "ieee",
     "The IEEE student branch at Manipal, supporting engineering students through talks, workshops and projects."),
]

STUDENTS = [
    ("Riya Sharma", "student1@example.com", "2409110001"),
    ("Arjun Nair", "student2@example.com", "2409110002"),
    ("Meera Iyer", "student3@example.com", "2409110003"),
    ("Kabir Shetty", "student4@example.com", "2409110004"),
    ("Ananya Rao", "student5@example.com", "2409110005"),
    ("Rohan Pai", "student6@example.com", "2409110006"),
]


def at(days: int, hour: int, minute: int = 0) -> datetime:
    """A time of day `days` from today, in IST."""
    day = datetime.now(IST).date() + timedelta(days=days)
    return datetime.combine(day, time(hour, minute), IST)


def event(club, title, category, venue, starts, hours, capacity, style, description, deadline=None):
    return Event(club_id=club.id, title=title, category=category, venue=venue,
                 starts_at=starts, ends_at=starts + timedelta(hours=hours),
                 registration_deadline=deadline or starts - timedelta(hours=2),
                 capacity=capacity, poster_style=style, status="published",
                 description=description)


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pw = hash_password(PASSWORD)

    admin = User(name="Eventify Admin", email="admin@example.com", reg_no="1000000000",
                 password_hash=hash_password("admin1234"), is_admin=True)
    db.add(admin)
    students = [User(name=n, email=e, reg_no=r, password_hash=pw) for n, e, r in STUDENTS]
    db.add_all(students)
    db.flush()

    clubs = {}
    for i, (name, short, category, handle, description) in enumerate(CLUBS, start=1):
        if handle in ADMIN_CLUBS:
            owner = admin
        else:
            owner = User(name=f"{short} Organizer", email=f"{handle}.organizer@example.com",
                         reg_no=f"20000000{i:02d}", password_hash=pw)
            db.add(owner)
            db.flush()
        club = Club(name=name, short_name=short, category=category, description=description,
                    contact_email=f"{handle}.organizer@example.com", owner_id=owner.id,
                    status="approved")
        db.add(club)
        db.flush()
        clubs[handle] = club

    now = datetime.now(IST).replace(second=0, microsecond=0)
    soon = now + timedelta(minutes=20)
    e = {
        "openmic": event(clubs["chords"], "After Class: Open Mic", "Music", "Student Plaza",
                         at(3, 18), 2.5, 60, "ember",
                         "Bring a song, a poem or a few jokes. Sign up for a five-minute slot on the night, "
                         "or just come for the music. A keyboard, two guitars and a cajón will be on stage."),
        "theatre": event(clubs["aaina"], "Stage Zero: Theatre Workshop", "Theatre", "Library Auditorium",
                         at(5, 16), 3, 35, "noir",
                         "A beginner-friendly workshop on voice, movement and stage presence. "
                         "No acting experience needed. Wear comfortable clothes."),
        "dance": event(clubs["blitzkrieg"], "Eight Counts: Dance Workshop", "Dance", "Activity Hall, Block 5",
                       at(6, 17, 30), 2, 40, "cobalt",
                       "Learn a short hip-hop routine from scratch, broken down eight counts at a time. "
                       "Open to all levels."),
        "photowalk": event(clubs["photography"], "Frame by Frame: Campus Photo Walk", "Photography",
                           "Meet at the Food Court entrance", at(2, 6, 30), 2, 2, "sage",
                           "An early-morning walk across campus to catch the light. Bring any camera, "
                           "phone cameras included. We will stop for composition tips along the way."),
        "quiz": event(clubs["ldq"], "The Friday Quiz", "Literary", "AB5 Seminar Hall",
                      at(8, 18), 2, 50, "mustard",
                      "A general quiz in teams of up to three, registered individually. "
                      "Six rounds covering books, films, sport, science and Manipal trivia."),
        "webapp": event(clubs["iecse"], "Build Your First Web App", "Technology", "NLH 201",
                        soon, 2, 40, "mint",
                        "A hands-on session where you build and deploy a small web app with HTML, CSS and "
                        "JavaScript. Bring a laptop with a code editor installed.",
                        deadline=soon - timedelta(minutes=5)),
        "ctf": event(clubs["mist"], "Capture the Flag: Beginner Edition", "Technology", "Lab 3, AB4",
                     at(10, 14), 4, 30, "terminal",
                     "An introductory CTF with challenges in web security, cryptography and forensics. "
                     "Hints are available, and no prior security experience is required."),
        "circuits": event(clubs["ieee"], "Circuits & Coffee", "Technology", "Innovation Centre",
                          at(12, 16), 2, 3, "navy",
                          "An informal evening of breadboarding simple circuits over coffee. "
                          "Components are provided, and you can take your circuit home."),
        "unplugged": event(clubs["chords"], "Unplugged Evening", "Music", "Student Plaza",
                           at(-7, 18), 2, 40, "ember",
                           "An acoustic evening with student performers and a short open session at the end."),
        "git": event(clubs["iecse"], "Git & GitHub Basics", "Technology", "NLH 204",
                     at(-14, 15), 2, 40, "mint",
                     "Version control from the ground up: commits, branches, pull requests and resolving conflicts."),
    }
    db.add_all(e.values())
    db.flush()

    def reg(ev, student, status="confirmed", checked_in=False, minutes_ago=60):
        db.add(Registration(
            event_id=ev.id, user_id=student.id, status=status,
            queued_at=now - timedelta(minutes=minutes_ago),
            ticket_token=new_ticket_token() if status == "confirmed" else None,
            checked_in_at=ev.starts_at + timedelta(minutes=5) if checked_in else None,
        ))

    s1, s2, s3, s4, s5, s6 = students
    reg(e["photowalk"], s3, minutes_ago=90)
    reg(e["photowalk"], s4, minutes_ago=80)
    reg(e["photowalk"], s5, "waitlisted", minutes_ago=70)
    reg(e["photowalk"], admin, "waitlisted", minutes_ago=60)
    reg(e["webapp"], admin)
    reg(e["webapp"], s1)
    reg(e["webapp"], s2)
    reg(e["webapp"], s6)
    for student in (s2, s3, s4):
        reg(e["openmic"], student)
    reg(e["quiz"], s5)
    reg(e["ctf"], s6)
    for student in (s1, s3, s4):
        reg(e["circuits"], student)
    for student, came in ((s1, True), (s2, True), (s3, False), (s4, True)):
        reg(e["unplugged"], student, checked_in=came)
    for student, came in ((s2, True), (s5, True), (s6, False)):
        reg(e["git"], student, checked_in=came)

    db.add(Club(name="Campus Board Games Society", short_name="Board Games", category="Other",
                description="A weekly meet-up for board game and card game fans, with games for beginners and regulars.",
                contact_email="student2@example.com", owner_id=s2.id, status="pending"))
    db.commit()
    db.close()
    print("Seeded: 8 clubs, 10 events, 6 students, 6 organizers, 1 admin (owns 2 clubs), 1 pending club application.")


if __name__ == "__main__":
    main()
