from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from db import database as db
from routers import auth, users, products, orders, inquiries, payments, builder, reviews, complaints


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.create_pool(settings.DATABASE_URL)
    print(f"[PrintHub] Database pool connected | env={settings.NODE_ENV}")
    yield
    await db.close_pool()
    print("[PrintHub] Database pool closed")


app = FastAPI(
    title="PrintHub API",
    version="1.0.0",
    description="PrintHub backend — FastAPI Python port",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api"

app.include_router(auth.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(products.router, prefix=PREFIX)
app.include_router(orders.router, prefix=PREFIX)
app.include_router(inquiries.router, prefix=PREFIX)
app.include_router(payments.router, prefix=PREFIX)
app.include_router(builder.router, prefix=PREFIX)
app.include_router(reviews.router, prefix=PREFIX)
app.include_router(complaints.router, prefix=PREFIX)


@app.get("/")
async def root():
    return {"message": "PrintHub API is running", "version": "1.0.0", "env": settings.NODE_ENV}
