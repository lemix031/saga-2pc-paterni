# flight-service/main.py
import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text

#kreiranje FastAPI aplikacije i pozivanje os modula za uzimaanje DATABASE_URL-a
app = FastAPI()
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

class BookReq(BaseModel):
    user_id: str

#na pocetku aplikacije, ako ne postoji tabela booking flights - kreiraj je
@app.on_event("startup")
def startup():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flight_bookings (
              id UUID PRIMARY KEY,
              user_id TEXT NOT NULL,
              status TEXT NOT NULL
            )
        """))

#kreiraj rezervaciju 
@app.post("/book")
def book(req: BookReq):
    booking_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO flight_bookings (id, user_id, status) VALUES (:id, :u, 'BOOKED')"),
            {"id": booking_id, "u": req.user_id},
        )
    return {"flight_id": booking_id}

#canceluj rezervaciju
@app.post("/cancel/{flight_id}")
def cancel(flight_id: str):
    with engine.begin() as conn:
        res = conn.execute(
            text("UPDATE flight_bookings SET status='CANCELLED' WHERE id=:id"),
            {"id": flight_id},
        )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="flight booking not found")
    return {"status": "cancelled"}
