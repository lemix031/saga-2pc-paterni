import os, uuid
import psycopg2
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

DBS = {
    "flight": os.environ["FLIGHT_DB_URL"],
    "hotel": os.environ["HOTEL_DB_URL"],
    "car": os.environ["CAR_DB_URL"],
}

DDL = """
CREATE TABLE IF NOT EXISTS bookings (
  id UUID PRIMARY KEY,
  trip_id UUID NOT NULL,
  user_id TEXT NOT NULL
);
"""
#kreiranje konekcije ka bazama, autocommit ostaje kao bool vrednost i menja se kroz faze 2PC-a
def conn(url, autocommit: bool):
    c = psycopg2.connect(url)
    c.autocommit = autocommit
    return c

#nije deo logike 2PC-a, samo se kreiraju tabele potrebne za simulaciju
@app.on_event("startup")
def startup():
    for url in DBS.values():
        with conn(url, True) as c:
            with c.cursor() as cur:
                cur.execute(DDL)

class Req(BaseModel):
    user_id: str

#potreban za 2PC u PostgreSQL
def gid(trip_id: str, name: str) -> str:
    return f"trip:{trip_id}:{name}"


@app.post("/2pc/commit")
def two_pc_commit(req: Req):
    trip_id = str(uuid.uuid4())
    booking_id = str(uuid.uuid4())

    # PHASE 1: spremi sve DB-ove
    for name, url in DBS.items():
        g = gid(trip_id, name)
        c = conn(url, False)
        try:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO bookings (id, trip_id, user_id) VALUES (%s,%s,%s)",
                    (booking_id, trip_id, req.user_id),
                )
                cur.execute("PREPARE TRANSACTION %s", (g,))
            c.close()
        except Exception:
            c.rollback()
            c.close()
            # ako prepare pukne, demo je dovoljan: ovde bi isao rollback prepared on previously prepared
            raise

    # PHASE 2: Sve što uđe u Prepared, to se i commituje
    for name, url in DBS.items():
        g = gid(trip_id, name)
        with conn(url, True) as c:
            with c.cursor() as cur:
                cur.execute("COMMIT PREPARED %s", (g,))

    return {"trip_id": trip_id, "status": "COMMITTED"}

@app.post("/2pc/prepare-only")
def two_pc_prepare_only(req: Req):
    trip_id = str(uuid.uuid4())
    booking_id = str(uuid.uuid4())

    # PHASE 1 only: Ovde se zapravo radi samo jedna faza a to je PREPARE svih tabela
    for name, url in DBS.items():
        g = gid(trip_id, name)
        c = conn(url, False)
        try:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO bookings (id, trip_id, user_id) VALUES (%s,%s,%s)",
                    (booking_id, trip_id, req.user_id),
                )
                cur.execute("PREPARE TRANSACTION %s", (g,))
            c.close()
        except Exception:
            c.rollback()
            c.close()
            raise

    return {"trip_id": trip_id, "status": "PREPARED_ONLY"}

@app.get("/2pc/prepared")
def prepared():
    out = {}
    for name, url in DBS.items():
        with conn(url, True) as c:
            with c.cursor() as cur:
                cur.execute("SELECT gid FROM pg_prepared_xacts ORDER BY prepared DESC")
                out[name] = [r[0] for r in cur.fetchall()]
    return out
