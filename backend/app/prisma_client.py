from prisma import Prisma

prisma = Prisma(auto_register=True)


async def get_db():
    if not prisma.is_connected():
        await prisma.connect()
    return prisma


async def connect_db():
    if not prisma.is_connected():
        await prisma.connect()
    await ensure_database_constraints()


async def disconnect_db():
    if prisma.is_connected():
        await prisma.disconnect()


async def ensure_database_constraints():
    await prisma.execute_raw(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS appointment_active_slot_unique
        ON "Appointment" ("doctor_id", "appointment_date", "start_time")
        WHERE "status" IN ('SCHEDULED', 'RESCHEDULED')
        """
    )
