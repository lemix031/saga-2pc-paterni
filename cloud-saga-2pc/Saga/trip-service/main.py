# trip-service/main.py (SAGA orchestration)
import os, httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
FLIGHT_URL = os.environ["FLIGHT_URL"]
HOTEL_URL = os.environ["HOTEL_URL"]
CAR_URL = os.environ["CAR_URL"]

class TripReq(BaseModel):
    user_id: str
    fail_hotel: bool = False
    fail_car: bool = False

@app.post("/book-trip")
async def book_trip(req: TripReq):
    #kljucno cuvanje state-a, on mora da zna sta je palo da bi za te idjeve napravio kompenzaciju
    #bez state-a nema ni kompenzacije
    state = {"flight_id": None, "hotel_id": None, "car_id": None}

    async with httpx.AsyncClient(timeout=5.0) as client:
        # flight
        try:
            #probaj da odradis post, ako se post desi ti uradi raise for status, proveri statusni kod
            #ako se desio statusni kod razlicit od 200 baci HTTP Exception koji se obradi kao flight failed
            r = await client.post(f"{FLIGHT_URL}/book", json={"user_id": req.user_id})
            r.raise_for_status()
            state["flight_id"] = r.json()["flight_id"]
        except Exception:
            raise HTTPException(500, "flight failed")

        # hotel
        try:
            r = await client.post(f"{HOTEL_URL}/book", json={"user_id": req.user_id, "fail": req.fail_hotel})
            r.raise_for_status()
            state["hotel_id"] = r.json()["hotel_id"]
        except Exception:
            await client.post(f"{FLIGHT_URL}/cancel/{state['flight_id']}")
            raise HTTPException(500, "hotel failed -> compensated flight")

        # car
        try:
            r = await client.post(f"{CAR_URL}/book", json={"user_id": req.user_id, "fail": req.fail_car})
            r.raise_for_status()
            state["car_id"] = r.json()["car_id"]
        except Exception:
            await client.post(f"{HOTEL_URL}/cancel/{state['hotel_id']}")
            await client.post(f"{FLIGHT_URL}/cancel/{state['flight_id']}")
            raise HTTPException(500, "car failed -> compensated hotel + flight")

    return {"status": "SUCCESS", **state}
