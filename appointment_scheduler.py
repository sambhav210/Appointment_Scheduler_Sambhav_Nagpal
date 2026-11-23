
import sqlite3
from datetime import datetime, timedelta

DB_NAME = "scheduler.db"
FMT = "%Y-%m-%d %H:%M"


def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                contact TEXT NOT NULL,
                service TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                notes TEXT DEFAULT '',
                status TEXT DEFAULT 'Booked'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminder_history (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                sent_at TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)


def read_datetime(prompt):
    try:
        return datetime.strptime(input(prompt).strip(), FMT)
    except ValueError:
        print("Invalid format! Use YYYY-MM-DD HH:MM")
        return None


def has_time_conflict(start, end, ignore_id=None):
    query = """
        SELECT appointment_id FROM appointments
        WHERE status='Booked'
        AND start_time < ? AND end_time > ?
    """
    params = [end.strftime(FMT), start.strftime(FMT)]

    if ignore_id is not None:
        query += " AND appointment_id != ?"
        params.append(ignore_id)

    with connect_db() as conn:
        return conn.execute(query, params).fetchone() is not None


def book_appointment():
    print("\n--- BOOK APPOINTMENT ---")

    name = input("Client name: ").strip()
    contact = input("Phone/email: ").strip()
    service = input("Service: ").strip()

    if not name or not contact or not service:
        print("All fields are required.")
        return

    start = read_datetime("Start date (YYYY-MM-DD HH:MM): ")

    if start is None or start <= datetime.now():
        print("Please enter a valid future date.")
        return

    try:
        duration = int(input("Duration in minutes (15-240): "))
        if not 15 <= duration <= 240:
            raise ValueError
    except ValueError:
        print("Enter duration between 15 and 240.")
        return

    end = start + timedelta(minutes=duration)

    if has_time_conflict(start, end):
        print("This time overlaps another appointment!")
        return

    notes = input("Additional notes: ").strip()

    with connect_db() as conn:
        cur = conn.execute("""
            INSERT INTO appointments
            (client_name, contact, service, start_time,
             end_time, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name, contact, service,
            start.strftime(FMT),
            end.strftime(FMT), notes
        ))

    print("Appointment booked successfully!")
    print("Appointment ID:", cur.lastrowid)


def list_appointments():
    with connect_db() as conn:
        rows = conn.execute("""
            SELECT * FROM appointments
            ORDER BY start_time
        """).fetchall()

    if not rows:
        print("No appointments found.")
        return

    print("\nID | CLIENT | SERVICE | DATE | STATUS")
    print("-" * 75)

    for r in rows:
        print(
            r["appointment_id"], "|",
            r["client_name"], "|",
            r["service"], "|",
            r["start_time"], "|",
            r["status"]
        )


def search_appointment():
    term = input("Enter client name or service: ").strip()

    with connect_db() as conn:
        rows = conn.execute("""
            SELECT * FROM appointments
            WHERE client_name LIKE ? OR service LIKE ?
            ORDER BY start_time
        """, (f"%{term}%", f"%{term}%")).fetchall()

    if not rows:
        print("No matching appointment found.")
        return

    for r in rows:
        print(
            "ID:", r["appointment_id"],
            "| Name:", r["client_name"],
            "| Service:", r["service"],
            "| Date:", r["start_time"],
            "| Status:", r["status"]
        )


def reschedule_appointment():
    try:
        aid = int(input("Enter appointment ID: "))
    except ValueError:
        print("Invalid ID.")
        return

    with connect_db() as conn:
        row = conn.execute("""
            SELECT * FROM appointments
            WHERE appointment_id=? AND status='Booked'
        """, (aid,)).fetchone()

    if row is None:
        print("Appointment not found.")
        return

    new_start = read_datetime("Enter new date (YYYY-MM-DD HH:MM): ")

    if new_start is None or new_start <= datetime.now():
        print("Invalid or past date.")
        return

    old_start = datetime.strptime(row["start_time"], FMT)
    old_end = datetime.strptime(row["end_time"], FMT)
    duration = old_end - old_start
    new_end = new_start + duration

    if has_time_conflict(new_start, new_end, aid):
        print("New time overlaps another appointment.")
        return

    with connect_db() as conn:
        conn.execute("""
            UPDATE appointments
            SET start_time=?, end_time=?
            WHERE appointment_id=?
        """, (new_start.strftime(FMT),
              new_end.strftime(FMT), aid))

    print("Appointment rescheduled successfully!")


def change_status():
    try:
        aid = int(input("Enter appointment ID: "))
    except ValueError:
        print("Invalid ID.")
        return

    print("1. Cancel appointment")
    print("2. Mark as completed")

    choice = input("Enter choice: ")

    status = {
        "1": "Cancelled",
        "2": "Completed"
    }.get(choice)

    if status is None:
        print("Invalid choice.")
        return

    with connect_db() as conn:
        cur = conn.execute("""
            UPDATE appointments
            SET status=?
            WHERE appointment_id=? AND status='Booked'
        """, (status, aid))

    if cur.rowcount:
        print("Appointment", status, "successfully!")
    else:
        print("Active appointment not found.")


def show_reminders():
    now = datetime.now()
    limit = now + timedelta(hours=24)

    with connect_db() as conn:
        rows = conn.execute("""
            SELECT * FROM appointments a
            WHERE a.status='Booked'
            AND a.start_time >= ?
            AND a.start_time <= ?
            AND NOT EXISTS (
                SELECT 1 FROM reminder_history r
                WHERE r.appointment_id=a.appointment_id
            )
            ORDER BY a.start_time
        """, (now.strftime(FMT), limit.strftime(FMT))).fetchall()

        if not rows:
            print("No new reminders in the next 24 hours.")
            return

        print("\n--- UPCOMING REMINDERS ---")

        for r in rows:
            message = (
                f"Reminder for {r['client_name']}: "
                f"{r['service']} at {r['start_time']}"
            )

            print(message)

            conn.execute("""
                INSERT INTO reminder_history
                (appointment_id, sent_at, message)
                VALUES (?, ?, ?)
            """, (r["appointment_id"], now.strftime(FMT), message))


def main():
    setup_database()

    while True:
        print("\n========== APPOINTMENT SCHEDULER ==========")
        print("1. Book appointment")
        print("2. View all appointments")
        print("3. Search appointment")
        print("4. Reschedule appointment")
        print("5. Cancel / Complete appointment")
        print("6. Check reminders")
        print("7. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            book_appointment()
        elif choice == "2":
            list_appointments()
        elif choice == "3":
            search_appointment()
        elif choice == "4":
            reschedule_appointment()
        elif choice == "5":
            change_status()
        elif choice == "6":
            show_reminders()
        elif choice == "7":
            print("Thank you for using Appointment Scheduler!")
            break
        else:
            print("Invalid choice!")


if __name__ == "__main__":
    main()
