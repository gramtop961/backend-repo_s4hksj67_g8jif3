import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User, Car, Order, Transaction, Notification, Reward

app = FastAPI(title="Car Marketplace API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
class ObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        try:
            return str(ObjectId(str(v)))
        except Exception:
            raise ValueError("Invalid ObjectId")

class LoginRequest(BaseModel):
    email: str

@app.get("/")
async def root():
    return {"message": "Car Marketplace Backend running"}

# Auth & Onboarding (simple email-based for demo)
@app.post("/auth/login")
async def login(payload: LoginRequest):
    users = db["user"].find_one({"email": payload.email}) if db else None
    if not users:
        # auto-create placeholder user as customer
        uid = create_document("user", User(role="customer", full_name="New User", email=payload.email).model_dump())
        return {"status": "created", "email": payload.email, "role": "customer", "id": uid}
    return {"status": "ok", "email": users["email"], "role": users.get("role", "customer"), "id": str(users.get("_id"))}

@app.post("/auth/onboard/customer")
async def onboard_customer(user: User):
    user.role = "customer"
    existing = db["user"].find_one({"email": user.email})
    if existing:
        db["user"].update_one({"_id": existing["_id"]}, {"$set": user.model_dump()})
        return {"status": "updated"}
    user_id = create_document("user", user)
    return {"status": "created", "id": user_id}

@app.post("/auth/onboard/owner")
async def onboard_owner(user: User):
    user.role = "owner"
    existing = db["user"].find_one({"email": user.email})
    if existing:
        db["user"].update_one({"_id": existing["_id"]}, {"$set": user.model_dump()})
        return {"status": "updated"}
    user_id = create_document("user", user)
    return {"status": "created", "id": user_id}

# Cars CRUD
@app.post("/cars")
async def create_car(car: Car):
    if not (car.for_sale or car.for_rent):
        raise HTTPException(status_code=400, detail="Car must be for sale or for rent")
    car_id = create_document("car", car)
    return {"id": car_id}

@app.get("/cars")
async def list_cars(
    q: Optional[str] = None,
    location: Optional[str] = None,
    car_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    mode: Optional[str] = None  # rent|sale
):
    flt = {}
    if q:
        flt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"brand": {"$regex": q, "$options": "i"}},
            {"model": {"$regex": q, "$options": "i"}},
        ]
    if location:
        flt["location"] = {"$regex": location, "$options": "i"}
    if car_type:
        flt["car_type"] = car_type
    if min_price is not None or max_price is not None:
        price_q = {}
        if mode == "sale":
            key = "sale_price"
        else:
            key = "price_per_day"
        if min_price is not None:
            price_q["$gte"] = min_price
        if max_price is not None:
            price_q["$lte"] = max_price
        flt[key] = price_q
    if mode == "sale":
        flt["for_sale"] = True
    if mode == "rent":
        flt["for_rent"] = True

    cars = list(db["car"].find(flt)) if db else []
    for c in cars:
        c["id"] = str(c.pop("_id"))
    return cars

@app.get("/cars/{car_id}")
async def get_car(car_id: str):
    car = db["car"].find_one({"_id": ObjectId(car_id)})
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    car["id"] = str(car.pop("_id"))
    return car

# Orders
@app.post("/orders")
async def create_order(order: Order):
    # Basic validation
    car = db["car"].find_one({"_id": ObjectId(order.car_id)})
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    order_id = create_document("order", order)
    # create notification for owner
    create_document("notification", Notification(
        email=order.owner_email,
        title="New order",
        message=f"You have a new {order.order_type} request"
    ))
    return {"id": order_id}

@app.get("/orders")
async def list_orders(email: Optional[str] = None, role: Optional[str] = None):
    flt = {}
    if email and role == "customer":
        flt["customer_email"] = email
    if email and role == "owner":
        flt["owner_email"] = email
    orders = list(db["order"].find(flt)) if db else []
    for o in orders:
        o["id"] = str(o.pop("_id"))
    return orders

@app.post("/orders/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    res = db["order"].update_one({"_id": ObjectId(order_id)}, {"$set": {"status": status}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"status": "ok"}

# Transactions
@app.post("/transactions")
async def create_transaction(tx: Transaction):
    tx_id = create_document("transaction", tx)
    # loyalty points
    pts = int(max(1, tx.amount // 10))
    existing = db["reward"].find_one({"email": tx.customer_email})
    if existing:
        new_points = existing.get("points", 0) + pts
        tier = "Bronze"
        if new_points >= 200: tier = "Platinum"
        elif new_points >= 120: tier = "Gold"
        elif new_points >= 60: tier = "Silver"
        db["reward"].update_one({"_id": existing["_id"]}, {"$set": {"points": new_points, "tier": tier}})
    else:
        create_document("reward", Reward(email=tx.customer_email, points=pts))
    return {"id": tx_id}

@app.get("/transactions")
async def list_transactions(email: Optional[str] = None):
    flt = {"$or": [{"customer_email": email}, {"owner_email": email}]} if email else {}
    txs = list(db["transaction"].find(flt)) if db else []
    for t in txs:
        t["id"] = str(t.pop("_id"))
    return txs

# Notifications
@app.get("/notifications")
async def get_notifications(email: str):
    items = list(db["notification"].find({"email": email})) if db else []
    for n in items:
        n["id"] = str(n.pop("_id"))
    return items

# Schema exposure for tooling
@app.get("/schema")
async def get_schema():
    # Simply reflect the collections from schemas.py via names
    return {
        "collections": ["user", "car", "order", "transaction", "notification", "reward"]
    }

@app.get("/test")
async def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
