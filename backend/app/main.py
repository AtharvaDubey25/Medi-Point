from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.prisma_client import connect_db, disconnect_db
from app.redis_client import init_redis, close_redis
from app.routers import auth, doctors, appointments, symptoms, admin
from app.background.medication_reminder import check_medication_reminders, check_appointment_reminders
from app.background.email_retry import process_email_queue

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await init_redis()

    scheduler.add_job(
        check_medication_reminders,
        "interval",
        minutes=settings.BACKGROUND_INTERVAL_MINUTES,
        id="medication_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        check_appointment_reminders,
        "cron",
        hour=8,
        minute=0,
        id="appointment_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        process_email_queue,
        "interval",
        minutes=1,
        id="email_retry",
        replace_existing=True,
    )
    scheduler.start()

    yield

    scheduler.shutdown()
    await close_redis()
    await disconnect_db()


app = FastAPI(
    title="Medi Point",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(symptoms.router)
app.include_router(admin.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "medi-point"}
