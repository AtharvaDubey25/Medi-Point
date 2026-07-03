import asyncio
import sqlite3
import datetime
import sys
import os

sys.path.append(r'c:\healthcare-appointment-platform\backend')

from app.prisma_client import connect_db, disconnect_db
from app.prisma_client import prisma

def to_datetime(val):
    if val is None:
        return datetime.datetime.now()
    if isinstance(val, int) or isinstance(val, float):
        # If timestamp is in milliseconds
        if val > 10000000000:
            return datetime.datetime.fromtimestamp(val / 1000.0, tz=datetime.timezone.utc)
        return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
    if isinstance(val, str):
        # Strip trailing space or offset representation
        cleaned = val.strip().replace('Z', '+00:00')
        try:
            return datetime.datetime.fromisoformat(cleaned)
        except ValueError:
            try:
                # Try parsing space instead of T separator
                return datetime.datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    return datetime.datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    print(f"Failed to parse datetime string: {val}", file=sys.stderr)
                    return datetime.datetime.now()
    return datetime.datetime.now()

async def main():
    print("Connecting to PostgreSQL/Supabase...")
    await connect_db()
    
    sqlite_db_path = r'c:\healthcare-appointment-platform\backend\prisma\prisma\dev.db'
    if not os.path.exists(sqlite_db_path):
        print(f"Error: SQLite database not found at {sqlite_db_path}")
        return
        
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    sqlite_cur = sqlite_conn.cursor()
    
    try:
        print("Migrating User table...")
        sqlite_cur.execute("SELECT id, email, password_hash, full_name, phone, role, is_active, google_calendar_token, created_at, updated_at FROM User;")
        for row in sqlite_cur.fetchall():
            exists = await prisma.user.find_first(where={"id": row[0]})
            if not exists:
                created_at = to_datetime(row[8])
                updated_at = to_datetime(row[9])
                await prisma.user.create(data={
                    "id": row[0],
                    "email": row[1],
                    "password_hash": row[2],
                    "full_name": row[3],
                    "phone": row[4],
                    "role": row[5],
                    "is_active": bool(row[6]),
                    "google_calendar_token": row[7],
                    "created_at": created_at,
                    "updated_at": updated_at
                })
                
        print("Migrating DoctorProfile table...")
        sqlite_cur.execute("SELECT id, user_id, specialization, qualification, experience_years, slot_duration_minutes, is_on_leave, bio, created_at FROM DoctorProfile;")
        for row in sqlite_cur.fetchall():
            exists = await prisma.doctorprofile.find_first(where={"id": row[0]})
            if not exists:
                created_at = to_datetime(row[8])
                await prisma.doctorprofile.create(data={
                    "id": row[0],
                    "user_id": row[1],
                    "specialization": row[2],
                    "qualification": row[3],
                    "experience_years": row[4],
                    "slot_duration_minutes": row[5],
                    "is_on_leave": bool(row[6]),
                    "bio": row[7],
                    "created_at": created_at
                })

        print("Migrating DoctorAvailability table...")
        sqlite_cur.execute("SELECT id, doctor_id, day_of_week, start_time, end_time, is_available FROM DoctorAvailability;")
        for row in sqlite_cur.fetchall():
            exists = await prisma.doctoravailability.find_first(where={"id": row[0]})
            if not exists:
                await prisma.doctoravailability.create(data={
                    "id": row[0],
                    "doctor_id": row[1],
                    "day_of_week": row[2],
                    "start_time": row[3],
                    "end_time": row[4],
                    "is_available": bool(row[5])
                })

        print("Migrating DoctorLeave table...")
        sqlite_cur.execute("SELECT id, doctor_id, leave_date, reason, created_at FROM DoctorLeave;")
        for row in sqlite_cur.fetchall():
            exists = await prisma.doctorleave.find_first(where={"id": row[0]})
            if not exists:
                leave_date = to_datetime(row[2])
                created_at = to_datetime(row[4])
                await prisma.doctorleave.create(data={
                    "id": row[0],
                    "doctor_id": row[1],
                    "leave_date": leave_date,
                    "reason": row[3],
                    "created_at": created_at
                })

        print("Migrating Appointment table...")
        sqlite_cur.execute("SELECT id, patient_id, doctor_id, appointment_date, start_time, end_time, status, google_calendar_event_id, doctor_calendar_event_id, cancellation_reason, created_at, updated_at FROM Appointment;")
        for row in sqlite_cur.fetchall():
            exists = await prisma.appointment.find_first(where={"id": row[0]})
            if not exists:
                apt_date = to_datetime(row[3])
                created_at = to_datetime(row[10])
                updated_at = to_datetime(row[11])
                await prisma.appointment.create(data={
                    "id": row[0],
                    "patient_id": row[1],
                    "doctor_id": row[2],
                    "appointment_date": apt_date,
                    "start_time": row[4],
                    "end_time": row[5],
                    "status": row[6],
                    "google_calendar_event_id": row[7],
                    "doctor_calendar_event_id": row[8],
                    "cancellation_reason": row[9],
                    "created_at": created_at,
                    "updated_at": updated_at
                })

        print("Migrating SymptomForm table...")
        sqlite_cur.execute("SELECT id, appointment_id, symptoms_text, pre_visit_summary, post_visit_notes, post_visit_prescription, post_visit_summary, created_at, updated_at FROM SymptomForm;")
        for row in sqlite_cur.fetchall():
            exists = await prisma.symptomform.find_first(where={"id": row[0]})
            if not exists:
                created_at = to_datetime(row[7])
                updated_at = to_datetime(row[8])
                await prisma.symptomform.create(data={
                    "id": row[0],
                    "appointment_id": row[1],
                    "symptoms_text": row[2],
                    "pre_visit_summary": row[3],
                    "post_visit_notes": row[4],
                    "post_visit_prescription": row[5],
                    "post_visit_summary": row[6],
                    "created_at": created_at,
                    "updated_at": updated_at
                })

        print("Migrating Medication table...")
        sqlite_cur.execute("SELECT id, appointment_id, medication_name, dosage, frequency, duration_days, start_date, last_reminded_at, notes, created_at FROM Medication;")
        for row in sqlite_cur.fetchall():
            exists = await prisma.medication.find_first(where={"id": row[0]})
            if not exists:
                start_date = to_datetime(row[6]) if row[6] else None
                last_reminded = to_datetime(row[7]) if row[7] else None
                created_at = to_datetime(row[9])
                await prisma.medication.create(data={
                    "id": row[0],
                    "appointment_id": row[1],
                    "medication_name": row[2],
                    "dosage": row[3],
                    "frequency": row[4],
                    "duration_days": row[5],
                    "start_date": start_date,
                    "last_reminded_at": last_reminded,
                    "notes": row[8],
                    "created_at": created_at
                })

        print("Resetting PostgreSQL sequences...")
        tables = ["User", "DoctorProfile", "DoctorAvailability", "DoctorLeave", "Appointment", "SymptomForm", "Medication"]
        for table in tables:
            query = f'SELECT setval(pg_get_serial_sequence(\'"{table}"\', \'id\'), coalesce(max(id), 1)) FROM "{table}";'
            await prisma.execute_raw(query)
            print(f"Reset sequence for table: {table}")

        print("Success: Data migration finished successfully!")
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        sqlite_conn.close()
        await disconnect_db()

if __name__ == "__main__":
    asyncio.run(main())
