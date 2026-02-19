# hotel-service/main.py
import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text

app = FastAPI()
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

class BookReq(BaseModel):
    user_id: str
    fail: bool = False  # za demo: pošalji {"user_id":"x","fail":true} da simuliraš grešku

@app.on_event("startup")
def startup():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS hotel_bookings (
              id UUID PRIMARY KEY,
              user_id TEXT NOT NULL,
              status TEXT NOT NULL
            )
        """))

@app.post("/book")
def book(req: BookReq):
    if req.fail:
        raise HTTPException(status_code=500, detail="simulated hotel failure")
    booking_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO hotel_bookings (id, user_id, status) VALUES (:id, :u, 'BOOKED')"),
            {"id": booking_id, "u": req.user_id},
        )
    return {"hotel_id": booking_id}

@app.post("/cancel/{hotel_id}")
def cancel(hotel_id: str):
    with engine.begin() as conn:
        res = conn.execute(
            text("UPDATE hotel_bookings SET status='CANCELLED' WHERE id=:id"),
            {"id": hotel_id},
        )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="hotel booking not found")
    return {"status": "cancelled"}
