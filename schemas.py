"""
Database Schemas for Car Marketplace (Rent/Buy/Sell)

Each Pydantic model represents a MongoDB collection. Collection name is the lowercase of the class name.
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, EmailStr

class User(BaseModel):
    role: Literal["customer", "owner"] = Field(..., description="Account type")
    full_name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    location: Optional[str] = Field(None, description="City/Country")
    avatar_url: Optional[str] = None
    # Onboarding details
    driver_license: Optional[str] = None  # for customers
    company_name: Optional[str] = None    # for owners
    verification_status: Literal["pending", "verified", "rejected"] = "pending"

class Car(BaseModel):
    owner_email: EmailStr
    title: str
    brand: str
    model: str
    year: int
    images: List[str] = []
    location: str
    car_type: Literal["sedan", "suv", "truck", "coupe", "hatchback", "van", "convertible", "electric", "hybrid", "other"] = "sedan"
    transmission: Literal["automatic", "manual"] = "automatic"
    fuel: Literal["petrol", "diesel", "electric", "hybrid", "other"] = "petrol"
    mileage: Optional[int] = None
    color: Optional[str] = None
    for_rent: bool = True
    for_sale: bool = False
    price_per_day: Optional[float] = None
    sale_price: Optional[float] = None
    description: Optional[str] = None
    available: bool = True

class Order(BaseModel):
    order_type: Literal["rent", "buy"]
    car_id: str
    customer_email: EmailStr
    owner_email: EmailStr
    status: Literal["pending", "accepted", "rejected", "completed"] = "pending"
    # rent-specific
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    pickup_location: Optional[str] = None
    total_amount: float

class Transaction(BaseModel):
    order_id: str
    customer_email: EmailStr
    owner_email: EmailStr
    amount: float
    currency: str = "USD"
    type: Literal["debit", "credit"] = "debit"
    description: Optional[str] = None

class Notification(BaseModel):
    email: EmailStr
    title: str
    message: str
    read: bool = False

class Reward(BaseModel):
    email: EmailStr
    points: int = 0
    tier: Literal["Bronze", "Silver", "Gold", "Platinum"] = "Bronze"
