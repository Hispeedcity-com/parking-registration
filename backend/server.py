from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import bcrypt
import cloudinary
import cloudinary.uploader
import certifi
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter
from starlette.concurrency import run_in_threadpool

from email_service import build_receipt_email_message, build_renewal_receipt_email_message, send_email_with_attachment
from receipt_renderer import generate_renewal_receipt_pdf

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env", override=True)

MONGO_URL = os.environ.get("MONGO_URL") or os.environ["MONGODB_URI"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Hispeedcity").strip()
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Hispeedcity2026@").strip()

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
    secure=True,
)

client = AsyncIOMotorClient(MONGO_URL, tlsCAFile=certifi.where() if 'localhost' not in MONGO_URL else None)
db = client[DB_NAME]


def parse_cors_origins(raw_value: str) -> list[str]:
    return [origin.strip().strip('"').strip("'") for origin in re.split(r'[\s,\\]+', raw_value) if origin.strip()]

app = FastAPI(title="Hi Speed City Smart Parking API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(os.environ.get("CORS_ORIGIN", "*")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


class VehicleIn(BaseModel):
    vehicleNumber: str
    vehicleModel: str
    vehicleType: str
    vehicleColor: str


class ApplicationStatus(str, Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"


class ApplicationBase(BaseModel):
    fullName: str
    phoneNumber: str
    email: EmailStr
    companyName: str
    staffId: Optional[str] = ""
    vehicleNumber: str
    vehicleModel: str
    vehicleType: str
    vehicleColor: str
    parkingType: str
    subscriptionPeriod: str
    totalAmount: int
    vehicles: list[VehicleIn] = []


class ApplicationOut(ApplicationBase):
    model_config = ConfigDict(extra="ignore")

    referenceNumber: str
    receiptUrl: str
    status: ApplicationStatus
    submittedAt: datetime
    updatedAt: datetime


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str
    confirmNewPassword: str


class StatusUpdateRequest(BaseModel):
    status: ApplicationStatus


class ParkingAvailabilityUpdateRequest(BaseModel):
    available: bool


class ParkingPrice(BaseModel):
    key: str
    parkingType: str
    label: str
    monthlyPrice: int


PARKING_TYPE_SETTINGS = [
    {
        'key': 'non_reserved',
        'parkingType': 'Non Reserved',
        'label': 'Non-Reserved Parking',
    },
    {
        'key': 'reserved',
        'parkingType': 'Reserved',
        'label': 'Reserved Parking',
    },
    {
        'key': 'premium',
        'parkingType': 'Premium',
        'label': 'Premium Parking',
    },
]

PARKING_TYPE_LOOKUP = {item['parkingType']: item for item in PARKING_TYPE_SETTINGS}
PARKING_KEY_LOOKUP = {item['key']: item for item in PARKING_TYPE_SETTINGS}
PARKING_PRICES = {
    'non_reserved': 159,
    'reserved': 212,
    'premium': 318,
}


def parking_type_to_key(parking_type: str | None) -> str | None:
    if not parking_type:
        return None
    config = PARKING_TYPE_LOOKUP.get(parking_type.strip())
    return config['key'] if config else None


def parking_type_to_label(parking_type: str | None) -> str:
    if not parking_type:
        return 'Parking Type'
    config = PARKING_TYPE_LOOKUP.get(parking_type.strip())
    return config['label'] if config else parking_type.strip()


async def seed_default_parking_settings() -> None:
    for config in PARKING_TYPE_SETTINGS:
        await db.parking_settings.update_one(
            {'key': config['key']},
            {
                '$setOnInsert': {
                    'key': config['key'],
                    'parkingType': config['parkingType'],
                    'label': config['label'],
                    'available': True,
                    'createdAt': now_utc(),
                    'updatedAt': now_utc(),
                }
            },
            upsert=True,
        )


async def get_parking_availability_records() -> list[dict[str, Any]]:
    docs = await db.parking_settings.find({}, {'_id': 0}).to_list(20)
    doc_map = {doc.get('key'): doc for doc in docs if doc.get('key')}
    records: list[dict[str, Any]] = []

    for config in PARKING_TYPE_SETTINGS:
        doc = doc_map.get(config['key'], {})
        records.append({
            'key': config['key'],
            'parkingType': config['parkingType'],
            'label': config['label'],
            'available': doc.get('available', True),
            'updatedAt': doc.get('updatedAt'),
        })

    return records


async def get_parking_availability_map() -> dict[str, dict[str, Any]]:
    return {record['key']: record for record in await get_parking_availability_records()}


def get_parking_price_records() -> list[dict[str, Any]]:
    return [
        {
            'key': config['key'],
            'parkingType': config['parkingType'],
            'label': config['label'],
            'monthlyPrice': PARKING_PRICES.get(config['key'], 0),
        }
        for config in PARKING_TYPE_SETTINGS
    ]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_jwt(admin: dict[str, Any]) -> str:
    payload = {
        "sub": str(admin["_id"]),
        "username": admin["username"],
        "iat": int(now_utc().timestamp()),
        "exp": int((now_utc().timestamp()) + 60 * 60 * 24 * 7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_from_header(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization token missing")

    token = authorization.split(" ", 1)[1].strip()
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


async def get_current_admin(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    payload = decode_jwt_from_header(authorization)
    admin_id: Any = payload["sub"]
    try:
        admin_id = ObjectId(admin_id)
    except Exception:
        pass
    admin = await db.admins.find_one({"_id": admin_id}, {"passwordHash": 0})
    if not admin:
        raise HTTPException(status_code=401, detail="Admin not found")
    return admin


async def seed_default_admin() -> None:
    existing_admin = await db.admins.find_one({"username": DEFAULT_ADMIN_USERNAME.lower()})
    admin_doc = {
        "username": DEFAULT_ADMIN_USERNAME.lower(),
        "passwordHash": hash_password(DEFAULT_ADMIN_PASSWORD),
        "createdAt": now_utc(),
    }
    if existing_admin:
        await db.admins.update_one({"_id": existing_admin["_id"]}, {"$set": admin_doc})
        return
    await db.admins.insert_one(admin_doc)


async def next_reference_number() -> str:
    year = now_utc().year
    counter_id = f"applications-{year}"
    counter = await db.counters.find_one_and_update(
        {"_id": counter_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    seq = counter["seq"] if counter and "seq" in counter else 1
    return f"SP-{year}-{seq:06d}"


def normalize_vehicles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    vehicles = payload.get("vehicles") or []
    if vehicles:
        return vehicles
    if all(payload.get(key) for key in ["vehicleNumber", "vehicleModel", "vehicleType", "vehicleColor"]):
        return [
            {
                "vehicleNumber": payload["vehicleNumber"],
                "vehicleModel": payload["vehicleModel"],
                "vehicleType": payload["vehicleType"],
                "vehicleColor": payload["vehicleColor"],
            }
        ]
    return []


def calculate_total_amount(parking_type: str, subscription_period: str, vehicle_count: int) -> int:
    parking_prices = {"Non Reserved": 159, "Reserved": 212, "Premium": 318}
    multipliers = {"Monthly": 1, "Quarterly": 3, "Yearly": 12}
    return parking_prices.get(parking_type, 0) * multipliers.get(subscription_period, 1) * max(vehicle_count, 1)


async def upload_receipt_to_cloudinary(file: UploadFile) -> str:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Receipt file is empty")
    buffer = BytesIO(content)
    result = cloudinary.uploader.upload(
        buffer,
        folder="hispeedcity/receipts",
        resource_type="auto",
    )
    return result["secure_url"]


@app.on_event("startup")
async def startup_event() -> None:
    await seed_default_admin()
    await seed_default_parking_settings()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    client.close()


@app.get("/api/")
async def root() -> dict[str, str]:
    return {"message": "Hi Speed City API is running"}


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"message": "ok"}


@app.post("/api/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate) -> StatusCheck:
    status_obj = StatusCheck(client_name=input.client_name)
    doc = status_obj.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj


@app.get("/api/status", response_model=list[StatusCheck])
async def get_status_checks() -> list[StatusCheck]:
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check.get("timestamp"), str):
            check["timestamp"] = datetime.fromisoformat(check["timestamp"])
    return status_checks


@app.post("/api/admin/login")
async def admin_login(request: AdminLoginRequest) -> dict[str, Any]:
    admin = await db.admins.find_one({"username": request.username.lower().strip()})
    if not admin or not verify_password(request.password, admin["passwordHash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt(admin)
    return {"message": "Login successful", "token": token, "admin": {"username": admin["username"]}}


@app.post("/api/admin/logout")
async def admin_logout(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, str]:
    return {"message": "Logout successful"}


@app.get("/api/admin/me")
async def admin_me(current_admin: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {"username": current_admin["username"]}


@app.put("/api/admin/change-password")
async def change_password(request: ChangePasswordRequest, current_admin: dict[str, Any] = Depends(get_current_admin)) -> dict[str, str]:
    if not request.currentPassword.strip() or not request.newPassword.strip() or not request.confirmNewPassword.strip():
        raise HTTPException(status_code=400, detail="All password fields are required")

    if request.newPassword != request.confirmNewPassword:
        raise HTTPException(status_code=400, detail="New password and confirmation do not match")

    if request.currentPassword == request.newPassword:
        raise HTTPException(status_code=400, detail="New password must be different from the current password")

    admin = await db.admins.find_one({"_id": current_admin["_id"]})
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    if not verify_password(request.currentPassword, admin["passwordHash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    await db.admins.update_one(
        {"_id": admin["_id"]},
        {"$set": {"passwordHash": hash_password(request.newPassword)}},
    )
    return {"message": "Password updated successfully"}


@app.get("/api/admin/dashboard/stats")
async def dashboard_stats(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, int]:
    total = await db.applications.count_documents({})
    pending = await db.applications.count_documents({"status": "Pending"})
    approved = await db.applications.count_documents({"status": "Approved"})
    rejected = await db.applications.count_documents({"status": "Rejected"})
    return {
        "totalApplications": total,
        "pendingApplications": pending,
        "approvedApplications": approved,
        "rejectedApplications": rejected,
    }


@app.get('/api/parking-availability')
async def get_public_parking_availability() -> dict[str, list[dict[str, Any]]]:
    return {'parkingAvailability': await get_parking_availability_records()}


@app.get('/api/admin/parking-availability')
async def get_admin_parking_availability(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, list[dict[str, Any]]]:
    return {'parkingAvailability': await get_parking_availability_records()}


@app.put('/api/admin/parking-availability/{parking_key}')
async def update_parking_availability(
    parking_key: str,
    request: ParkingAvailabilityUpdateRequest,
    _: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, list[dict[str, Any]]]:
    config = PARKING_KEY_LOOKUP.get(parking_key)
    if not config:
        raise HTTPException(status_code=404, detail='Parking type not found')

    await db.parking_settings.update_one(
        {'key': parking_key},
        {
            '$set': {
                'available': request.available,
                'updatedAt': now_utc(),
            },
            '$setOnInsert': {
                'key': parking_key,
                'parkingType': config['parkingType'],
                'label': config['label'],
                'createdAt': now_utc(),
            },
        },
        upsert=True,
    )

    return {'parkingAvailability': await get_parking_availability_records()}


@app.get("/api/admin/applications")
async def list_applications(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, list[dict[str, Any]]]:
    applications = await db.applications.find({}, {"_id": 0}).sort("submittedAt", -1).to_list(1000)
    return {"applications": applications}


@app.get("/api/admin/applications/{reference_number}")
async def get_application(reference_number: str, _: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    application = await db.applications.find_one({"referenceNumber": reference_number}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"application": application}


@app.patch("/api/admin/applications/{reference_number}/status")
async def update_application_status(reference_number: str, request: StatusUpdateRequest, _: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    result = await db.applications.find_one_and_update(
        {"referenceNumber": reference_number},
        {"$set": {"status": request.status.value, "updatedAt": now_utc()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")
    result.pop("_id", None)
    return {"message": "Application status updated", "application": result}


@app.get("/api/applications/reference/{reference_number}")
async def get_public_application(reference_number: str) -> dict[str, Any]:
    application = await db.applications.find_one({"referenceNumber": reference_number}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime, timezone
from bson import ObjectId
from io import BytesIO
import os
import uuid
import bcrypt
import certifi
import jwt
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from pymongo.errors import PyMongoError

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

MONGO_URL = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URL')
if not MONGO_URL:
    raise RuntimeError('MONGODB_URI is required')


def parse_cors_origins(raw_value: str) -> list[str]:
    return [origin.strip().strip('"').strip("'") for origin in raw_value.split(',') if origin.strip()]


DB_NAME = os.environ.get('DB_NAME', 'hispeedcity')
JWT_SECRET = os.environ.get('JWT_SECRET', 'change-me')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'Hispeedcity')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Hispeedcity2026@')
CORS_ORIGINS = parse_cors_origins(os.environ.get('CORS_ORIGIN', os.environ.get('CORS_ORIGINS', '*')))
MONGO_TIMEOUT_MS = int(os.environ.get('MONGO_TIMEOUT_MS', '5000'))

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True,
)

client = AsyncIOMotorClient(
    MONGO_URL,
    tlsCAFile=certifi.where() if 'localhost' not in MONGO_URL else None,
    serverSelectionTimeoutMS=MONGO_TIMEOUT_MS,
    connectTimeoutMS=MONGO_TIMEOUT_MS,
    socketTimeoutMS=MONGO_TIMEOUT_MS,
)
db = client[DB_NAME]

app = FastAPI()
api_router = APIRouter(prefix='/api')

STATUS_PENDING = 'Pending'
STATUS_APPROVED = 'Approved'
STATUS_REJECTED = 'Rejected'
ALLOWED_STATUSES = {STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED}


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc = dict(doc)
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc


def to_application_response(doc: Dict[str, Any]) -> Dict[str, Any]:
    return serialize_doc(doc)


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def normalize_email_address(raw_value: Any) -> str:
    email = str(raw_value or '').strip()
    if not email:
        raise HTTPException(status_code=400, detail='Email address is required')

    try:
        validated_email = TypeAdapter(EmailStr).validate_python(email)
    except Exception as exc:
        raise HTTPException(status_code=400, detail='Invalid email address') from exc

    return str(validated_email)


def generate_receipt_number(renewal_reference: str) -> str:
    normalized_reference = str(renewal_reference or '').strip().replace(' ', '-')
    suffix = normalized_reference or uuid.uuid4().hex[:10].upper()
    return f'RCPT-{suffix}'


def normalize_required_text(raw_value: Any, field_name: str) -> str:
    value = str(raw_value or '').strip()
    if not value:
        raise HTTPException(status_code=400, detail=f'{field_name} is required')
    return value


def coerce_positive_int(raw_value: Any, field_name: str) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f'{field_name} must be a whole number') from exc

    if value <= 0:
        raise HTTPException(status_code=400, detail=f'{field_name} must be greater than zero')
    return value


def create_token(username: str) -> str:
    payload = {
        'sub': username,
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def require_admin(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Authorization token missing')
    token = authorization.split(' ', 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload['sub']
    except Exception:
        raise HTTPException(status_code=401, detail='Invalid or expired token')


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str
    confirmNewPassword: str


class StatusUpdateRequest(BaseModel):
    status: str


class ApplicationApprovalRequest(BaseModel):
    companyAddress: str

class RenewalCreateResponse(BaseModel):
    message: str
    renewalReference: str
    email: Optional[EmailStr] = None
    status: str
    submittedAt: datetime


class RenewalApprovalRequest(BaseModel):
    companyName: str
    companyAddress: str
    receiptNumber: Optional[str] = ""
    productMonth: str
    parkingType: str
    quantity: int
    unitPrice: int
    totalAmount: int
    additionalNotes: Optional[str] = ""


class RenewalEmailStatusUpdate(BaseModel):
    emailStatus: str
    emailSentAt: Optional[datetime] = None
    emailErrorMessage: Optional[str] = None
    emailProviderMessageId: Optional[str] = None


class ApplicationCreateResponse(BaseModel):
    message: str
    referenceNumber: str
    status: str
    submittedAt: datetime


@api_router.get('/')
async def root():
    return {'message': 'Hi Speed City API is running'}


@api_router.get('/health')
async def health():
    return {'message': 'ok'}


@api_router.get('/health/db')
async def database_health():
    try:
        await db.command('ping')
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail='Database is not reachable') from exc
    return {'message': 'database ok'}


@api_router.post('/admin/login')
async def admin_login(payload: AdminLoginRequest):
    try:
        admin = await db.admins.find_one({'username': payload.username})
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail='Database is not reachable') from exc

    if not admin or not verify_password(payload.password, admin['passwordHash']):
        raise HTTPException(status_code=401, detail='Invalid credentials')

    token = create_token(admin['username'])
    return {'message': 'Login successful', 'token': token, 'admin': {'username': admin['username']}}


@api_router.post('/admin/logout')
async def admin_logout(_: str = Depends(require_admin)):
    return {'message': 'Logout successful'}


@api_router.get('/admin/me')
async def admin_me(username: str = Depends(require_admin)):
    return {'username': username}


@api_router.put('/admin/change-password')
async def change_password(payload: ChangePasswordRequest, username: str = Depends(require_admin)):
    if not payload.currentPassword.strip() or not payload.newPassword.strip() or not payload.confirmNewPassword.strip():
        raise HTTPException(status_code=400, detail='All password fields are required')

    if payload.newPassword != payload.confirmNewPassword:
        raise HTTPException(status_code=400, detail='New password and confirmation do not match')

    if payload.currentPassword == payload.newPassword:
        raise HTTPException(status_code=400, detail='New password must be different from the current password')

    admin = await db.admins.find_one({'username': username})
    if not admin:
        raise HTTPException(status_code=404, detail='Admin account not found')

    if not verify_password(payload.currentPassword, admin['passwordHash']):
        raise HTTPException(status_code=400, detail='Current password is incorrect')

    new_hash = hash_password(payload.newPassword).decode('utf-8')
    await db.admins.update_one({'_id': admin['_id']}, {'$set': {'passwordHash': new_hash}})
    return {'message': 'Password updated successfully'}


@api_router.get('/admin/dashboard/stats')
async def dashboard_stats(_: str = Depends(require_admin)):
    total = await db.applications.count_documents({})
    pending = await db.applications.count_documents({'status': STATUS_PENDING})
    approved = await db.applications.count_documents({'status': STATUS_APPROVED})
    rejected = await db.applications.count_documents({'status': STATUS_REJECTED})
    total_renewals = await db.renewals.count_documents({})
    pending_renewals = await db.renewals.count_documents({'status': STATUS_PENDING})
    approved_renewals = await db.renewals.count_documents({'status': STATUS_APPROVED})
    rejected_renewals = await db.renewals.count_documents({'status': STATUS_REJECTED})
    return {
        'totalApplications': total,
        'pendingApplications': pending,
        'approvedApplications': approved,
        'rejectedApplications': rejected,
        'totalRenewals': total_renewals,
        'pendingRenewals': pending_renewals,
        'approvedRenewals': approved_renewals,
        'rejectedRenewals': rejected_renewals,
    }


@api_router.get('/parking-availability')
async def get_public_parking_availability():
    return {'parkingAvailability': await get_parking_availability_records()}


@api_router.get('/parking-prices')
async def get_public_parking_prices():
    return {'parkingPrices': get_parking_price_records()}


@api_router.get('/admin/parking-availability')
async def get_admin_parking_availability(_: str = Depends(require_admin)):
    return {'parkingAvailability': await get_parking_availability_records()}


@api_router.put('/admin/parking-availability/{parking_key}')
async def update_parking_availability(
    parking_key: str,
    payload: ParkingAvailabilityUpdateRequest,
    _: str = Depends(require_admin),
):
    config = PARKING_KEY_LOOKUP.get(parking_key)
    if not config:
        raise HTTPException(status_code=404, detail='Parking type not found')

    await db.parking_settings.update_one(
        {'key': parking_key},
        {
            '$set': {
                'available': payload.available,
                'updatedAt': datetime.now(timezone.utc),
            },
            '$setOnInsert': {
                'key': parking_key,
                'parkingType': config['parkingType'],
                'label': config['label'],
                'createdAt': datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )

    return {'parkingAvailability': await get_parking_availability_records()}


@api_router.get('/admin/applications')
async def list_applications(_: str = Depends(require_admin)):
    cursor = db.applications.find({}).sort('submittedAt', -1)
    applications = []
    async for doc in cursor:
        applications.append(to_application_response(doc))
    return {'applications': applications}


@api_router.get('/admin/applications/{reference_number}')
async def get_application(reference_number: str, _: str = Depends(require_admin)):
    application = await db.applications.find_one({'referenceNumber': reference_number})
    if not application:
        raise HTTPException(status_code=404, detail='Application not found')
    return {'application': to_application_response(application)}


@api_router.patch('/admin/applications/{reference_number}/status')
async def update_application_status(reference_number: str, payload: StatusUpdateRequest, _: str = Depends(require_admin)):
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail='Invalid status value')

    result = await db.applications.find_one_and_update(
        {'referenceNumber': reference_number},
        {'$set': {'status': payload.status, 'updatedAt': datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail='Application not found')
    return {'message': 'Application status updated', 'application': to_application_response(result)}


@api_router.post('/admin/applications/{reference_number}/approve')
async def approve_application(
    reference_number: str,
    payload: ApplicationApprovalRequest,
    username: str = Depends(require_admin),
):
    application = await db.applications.find_one({'referenceNumber': reference_number})
    if not application:
        raise HTTPException(status_code=404, detail='Application not found')

    if str(application.get('applicationType') or 'registration').strip().lower() != 'registration':
        raise HTTPException(status_code=400, detail='Approval receipt form is only available for New Registration requests')

    if application.get('status') == STATUS_APPROVED:
        raise HTTPException(status_code=400, detail='Application is already approved')

    company_address = normalize_required_text(payload.companyAddress, 'Company Address')
    receipt_document = build_registration_receipt_document(application, company_address, username)

    try:
        receipt_artifact = await generate_renewal_receipt_pdf(receipt_document)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to generate registration receipt PDF: {exc}') from exc

    email_status = 'Failed'
    email_sent_at = None
    email_error_message = None
    email_provider_message_id = None

    try:
        email_text, email_html = build_receipt_email_message(
            str(application.get('fullName') or 'Customer'),
            receipt_document['receiptNumber'],
        )
        email_result = await run_in_threadpool(
            send_email_with_attachment,
            to_email=str(application.get('email') or ''),
            subject='Parking Renewal Receipt',
            text_body=email_text,
            html_body=email_html,
            attachment_filename=f"{receipt_document['receiptNumber']}.pdf",
            attachment_bytes=receipt_artifact.pdf_bytes,
            from_email='hi@hispeedcity.com',
        )
        email_status = email_result.status
        email_sent_at = email_result.sent_at
        email_provider_message_id = email_result.provider_message_id
    except Exception as exc:
        email_error_message = str(exc)

    approved_at = datetime.now(timezone.utc)
    result = await db.applications.find_one_and_update(
        {'referenceNumber': reference_number},
        {
            '$set': {
                'status': STATUS_APPROVED,
                'receiptInfo': receipt_document,
                'approvedBy': username,
                'approvedAt': approved_at,
                'emailStatus': email_status,
                'emailSentAt': email_sent_at,
                'emailErrorMessage': email_error_message,
                'emailProviderMessageId': email_provider_message_id,
                'updatedAt': approved_at,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        raise HTTPException(status_code=404, detail='Application not found')

    result.pop('_id', None)
    return {
        'message': 'Application approved successfully',
        'receiptPdfGenerated': True,
        'receiptPdfPath': str(receipt_artifact.pdf_path),
        'receiptPdfSizeBytes': len(receipt_artifact.pdf_bytes),
        'emailStatus': email_status,
        'emailSentAt': email_sent_at,
        'emailErrorMessage': email_error_message,
        'application': to_application_response(result),
    }


def calculate_total_amount(parking_type: str, subscription_period: str, vehicle_count: int) -> int:
    parking_prices = {
        'Non Reserved': 159,
        'Reserved': 212,
        'Premium': 318,
    }
    multipliers = {
        'Monthly': 1,
        'Quarterly': 3,
        'Half-Year': 6,
        'Half Year': 6,
        'Yearly': 12,
    }
    return parking_prices.get(parking_type, 0) * multipliers.get(subscription_period, 1) * max(vehicle_count, 1)


def get_registration_receipt_totals(application: dict[str, Any]) -> tuple[int, int, int]:
    parking_type = str(application.get('parkingType') or '').strip()
    subscription_period = str(application.get('subscriptionPeriod') or '').strip()
    vehicles = application.get('vehicles') or normalize_vehicles(application)
    quantity = max(len(vehicles), 1)
    unit_price = PARKING_PRICES.get(parking_type_to_key(parking_type) or '', 0)
    multipliers = {
        'Monthly': 1,
        'Quarterly': 3,
        'Half-Year': 6,
        'Half Year': 6,
        'Yearly': 12,
    }
    total_amount = unit_price * multipliers.get(subscription_period, 1) * quantity
    return unit_price, quantity, total_amount


def build_registration_receipt_document(application: dict[str, Any], company_address: str, approved_by: str) -> dict[str, Any]:
    unit_price, quantity, total_amount = get_registration_receipt_totals(application)
    vehicles = application.get('vehicles') or normalize_vehicles(application)
    vehicle_plate_numbers = [
        str(vehicle.get('vehicleNumber') or '').strip().upper()
        for vehicle in vehicles
        if str(vehicle.get('vehicleNumber') or '').strip()
    ]
    if not vehicle_plate_numbers and application.get('vehicleNumber'):
        vehicle_plate_numbers = [str(application.get('vehicleNumber')).strip().upper()]

    return {
        'renewalType': application.get('parkingType') or 'Individual Renewal',
        'customerName': application.get('fullName') or '',
        'customerEmail': application.get('email') or '',
        'companyName': application.get('companyName') or '',
        'companyAddress': company_address,
        'receiptNumber': generate_receipt_number(application.get('referenceNumber') or ''),
        'parkingType': application.get('parkingType') or 'Individual Renewal',
        'subscriptionMonth': application.get('subscriptionPeriod') or '',
        'vehiclePlateNumbers': vehicle_plate_numbers,
        'quantity': quantity,
        'unitPrice': unit_price,
        'totalAmount': total_amount,
        'additionalNotes': '-',
        'approvedBy': approved_by,
        'approvedAt': datetime.now(timezone.utc),
        'grandTotal': total_amount,
    }


async def upload_receipt(file: UploadFile) -> str:
    contents = await file.read()
    result = cloudinary.uploader.upload(
        contents,
        resource_type='auto',
        folder='hispeedcity/receipts',
        public_id=f'receipt-{uuid.uuid4().hex}',
    )
    return result['secure_url']



async def upload_renewal_receipt(file: UploadFile) -> str:
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail='Receipt file is empty')

    result = cloudinary.uploader.upload(
        contents,
        resource_type='auto',
        folder='hispeedcity/renewals',
        public_id=f'renewal-receipt-{uuid.uuid4().hex}',
    )
    return result['secure_url']


def normalize_plate_numbers(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned = []
    for value in values:
        plate = str(value or '').strip().upper()
        if plate:
            cleaned.append(plate)
    return list(dict.fromkeys(cleaned))


def normalize_tenant_plate_groups(values: Any) -> dict[str, list[str]]:
    if not isinstance(values, dict):
        return {}
    grouped: dict[str, list[str]] = {}
    for key in ('non_reserved', 'reserved', 'premium'):
        grouped[key] = normalize_plate_numbers(values.get(key, []))
    return grouped


def calculate_tenant_total(quantities: dict[str, int], price_records: list[dict[str, Any]]) -> dict[str, int]:
    price_map = {item['key']: int(item.get('monthlyPrice', 0)) for item in price_records}
    totals = {
        'non_reservedTotal': int(quantities.get('non_reserved', 0)) * price_map.get('non_reserved', 0),
        'reservedTotal': int(quantities.get('reserved', 0)) * price_map.get('reserved', 0),
        'premiumTotal': int(quantities.get('premium', 0)) * price_map.get('premium', 0),
    }
    totals['grandTotal'] = totals['non_reservedTotal'] + totals['reservedTotal'] + totals['premiumTotal']
    return totals


async def next_renewal_reference() -> str:
    year = datetime.now(timezone.utc).year
    counter_id = f'renewals-{year}'
    counter = await db.counters.find_one_and_update(
        {'_id': counter_id},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True,
    )
    if not counter:
        counter = {'seq': 1}
    sequence = counter.get('seq', 1)
    return f'RN-{year}-{sequence:06d}'


@api_router.post('/renewals', response_model=RenewalCreateResponse)
async def create_individual_renewal(
    renewalData: str = Form(...),
    receipt: Optional[UploadFile] = File(None),
):
    import json

    try:
        payload = json.loads(renewalData)
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid renewal data')

    renewal_type = str(payload.get('renewalType') or '').strip() or 'Individual'
    if renewal_type != 'Individual':
        raise HTTPException(status_code=400, detail='Only Individual renewal is supported at this time')

    full_name = str(payload.get('fullName') or '').strip()
    if not full_name:
        raise HTTPException(status_code=400, detail='Full Name is required')

    email = normalize_email_address(payload.get('email'))

    month_note = str(payload.get('renewalMonthNote') or '').strip()
    if not month_note:
        raise HTTPException(status_code=400, detail='Renewal Month / Payment Note is required')

    raw_plates = payload.get('vehiclePlateNumbers')
    if not isinstance(raw_plates, list):
        raise HTTPException(status_code=400, detail='Vehicle plate numbers must be provided as a list')

    cleaned_plates = []
    for plate in raw_plates:
        cleaned = str(plate or '').strip().upper()
        if cleaned:
            cleaned_plates.append(cleaned)

    # Preserve input order while removing duplicates.
    unique_plates = list(dict.fromkeys(cleaned_plates))

    if not unique_plates:
        raise HTTPException(status_code=400, detail='At least one vehicle plate number is required')
    if len(unique_plates) > 3:
        raise HTTPException(status_code=400, detail='A maximum of 3 vehicle plate numbers is allowed')

    if receipt is None:
        raise HTTPException(status_code=400, detail='Payment receipt is required')

    receipt_url = await upload_renewal_receipt(receipt)
    submitted_at = datetime.now(timezone.utc)
    renewal_reference = await next_renewal_reference()

    renewal_doc = {
        'renewalReference': renewal_reference,
        'renewalType': 'Individual',
        'fullName': full_name,
        'email': email,
        'vehiclePlateNumbers': unique_plates,
        'renewalMonthNote': month_note,
        'receiptUrl': receipt_url,
        'status': STATUS_PENDING,
        'submittedAt': submitted_at,
        'updatedAt': submitted_at,
    }

    await db.renewals.insert_one(renewal_doc)

    return RenewalCreateResponse(
        message='Renewal request submitted successfully',
        renewalReference=renewal_reference,
        email=email,
        status=STATUS_PENDING,
        submittedAt=submitted_at,
    )


@api_router.post('/renewals/tenant', response_model=RenewalCreateResponse)
async def create_tenant_renewal(
    renewalData: str = Form(...),
    receipt: Optional[UploadFile] = File(None),
):
    import json

    try:
        payload = json.loads(renewalData)
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid renewal data')

    renewal_type = str(payload.get('renewalType') or '').strip() or 'Tenant'
    if renewal_type != 'Tenant':
        raise HTTPException(status_code=400, detail='Only Tenant renewal is supported at this time')

    company_name = str(payload.get('companyName') or '').strip()
    contact_person = str(payload.get('contactPerson') or '').strip()
    email = normalize_email_address(payload.get('email'))
    phone_number = str(payload.get('phoneNumber') or '').strip()
    month_note = str(payload.get('renewalMonthNote') or '').strip()
    if not all([company_name, contact_person, email, phone_number, month_note]):
        raise HTTPException(status_code=400, detail='All company and contact fields are required')

    quantities_raw = payload.get('parkingQuantities')
    if not isinstance(quantities_raw, dict):
        raise HTTPException(status_code=400, detail='Parking quantities are required')

    try:
        quantities = {
            'non_reserved': max(0, int(quantities_raw.get('non_reserved', 0) or 0)),
            'reserved': max(0, int(quantities_raw.get('reserved', 0) or 0)),
            'premium': max(0, int(quantities_raw.get('premium', 0) or 0)),
        }
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail='Parking quantities must be whole numbers')

    plate_groups = normalize_tenant_plate_groups(payload.get('vehiclePlateNumbers'))
    for key, quantity in quantities.items():
        if quantity > 0 and len(plate_groups.get(key, [])) != quantity:
            raise HTTPException(status_code=400, detail=f'{key.replace("_", " ").title()} vehicle plate list must match the selected quantity')

    price_records = get_parking_price_records()
    totals = calculate_tenant_total(quantities, price_records)

    if receipt is None:
        raise HTTPException(status_code=400, detail='Payment receipt is required')

    receipt_url = await upload_renewal_receipt(receipt)
    submitted_at = datetime.now(timezone.utc)
    renewal_reference = await next_renewal_reference()

    renewal_doc = {
        'renewalReference': renewal_reference,
        'renewalType': 'Tenant',
        'companyName': company_name,
        'contactPerson': contact_person,
        'email': email,
        'phoneNumber': phone_number,
        'renewalMonthNote': month_note,
        'parkingQuantities': quantities,
        'vehiclePlateNumbers': plate_groups,
        'pricingBreakdown': {
            'parkingPrices': {item['key']: item['monthlyPrice'] for item in price_records},
            **totals,
        },
        'receiptUrl': receipt_url,
        'status': STATUS_PENDING,
        'submittedAt': submitted_at,
        'updatedAt': submitted_at,
    }

    await db.renewals.insert_one(renewal_doc)

    return RenewalCreateResponse(
        message='Renewal request submitted successfully',
        renewalReference=renewal_reference,
        email=email,
        status=STATUS_PENDING,
        submittedAt=submitted_at,
    )


@api_router.get('/admin/renewals')
async def list_renewals(_: str = Depends(require_admin)):
    cursor = db.renewals.find({}).sort('submittedAt', -1)
    renewals = []
    async for doc in cursor:
        renewals.append(serialize_doc(doc))
    return {'renewals': renewals}


@api_router.get('/admin/renewals/{renewal_reference}')
async def get_renewal(renewal_reference: str, _: str = Depends(require_admin)):
    renewal = await db.renewals.find_one({'renewalReference': renewal_reference})
    if not renewal:
        raise HTTPException(status_code=404, detail='Renewal request not found')
    return {'renewal': serialize_doc(renewal)}


@api_router.patch('/admin/renewals/{renewal_reference}/status')
async def update_renewal_status(
    renewal_reference: str,
    payload: StatusUpdateRequest,
    _: str = Depends(require_admin),
):
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail='Invalid status value')

    result = await db.renewals.find_one_and_update(
        {'renewalReference': renewal_reference},
        {'$set': {'status': payload.status, 'updatedAt': datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail='Renewal request not found')

    return {'message': 'Renewal status updated', 'renewal': serialize_doc(result)}


@api_router.post('/admin/renewals/{renewal_reference}/approve')
async def approve_renewal(
    renewal_reference: str,
    payload: RenewalApprovalRequest,
    username: str = Depends(require_admin),
):
    renewal = await db.renewals.find_one({'renewalReference': renewal_reference})
    if not renewal:
        raise HTTPException(status_code=404, detail='Renewal request not found')

    if str(renewal.get('renewalType') or '').strip() != 'Individual':
        raise HTTPException(status_code=400, detail='Approval receipt form is only available for Individual renewal requests')

    if renewal.get('status') == STATUS_APPROVED:
        raise HTTPException(status_code=400, detail='Renewal request is already approved')

    company_name = normalize_required_text(payload.companyName, 'Company Name')
    company_address = normalize_required_text(payload.companyAddress, 'Company Address')
    product_month = normalize_required_text(payload.productMonth, 'Product / Subscription Month')
    parking_type = normalize_required_text(payload.parkingType, 'Parking Type')
    receipt_number = str(payload.receiptNumber or '').strip() or generate_receipt_number(renewal_reference)
    additional_notes = str(payload.additionalNotes or '').strip()
    quantity = coerce_positive_int(payload.quantity, 'Quantity')
    unit_price = coerce_positive_int(payload.unitPrice, 'Unit Price')
    total_amount = coerce_positive_int(payload.totalAmount, 'Total Amount')

    expected_total = quantity * unit_price
    if total_amount != expected_total:
        raise HTTPException(status_code=400, detail='Total Amount must equal Quantity multiplied by Unit Price')

    customer_name = str(renewal.get('fullName') or renewal.get('contactPerson') or '').strip()
    customer_email = str(renewal.get('email') or '').strip()
    vehicle_plate_numbers = renewal.get('vehiclePlateNumbers') or []

    receipt_info = {
        'customerName': customer_name,
        'customerEmail': customer_email,
        'vehiclePlateNumbers': vehicle_plate_numbers,
        'companyName': company_name,
        'companyAddress': company_address,
        'receiptNumber': receipt_number,
        'productMonth': product_month,
        'parkingType': parking_type,
        'quantity': quantity,
        'unitPrice': unit_price,
        'totalAmount': total_amount,
        'additionalNotes': additional_notes,
        'approvedBy': username,
        'approvedAt': datetime.now(timezone.utc),
        'lineItems': [
            {
                'item': 1,
                'productName': parking_type,
                'description': product_month,
                'qty': quantity,
                'unitPrice': unit_price,
                'totalPrice': total_amount,
            }
        ],
    }

    try:
        receipt_artifact = await generate_renewal_receipt_pdf(renewal, receipt_info=receipt_info)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to generate renewal receipt PDF: {exc}') from exc

    email_status = 'Failed'
    email_sent_at = None
    email_error_message = None
    email_provider_message_id = None

    try:
        email_text, email_html = build_renewal_receipt_email_message(customer_name or 'Customer', receipt_number)
        email_result = await run_in_threadpool(
            send_email_with_attachment,
            to_email=customer_email,
            subject='Parking Renewal Receipt',
            text_body=email_text,
            html_body=email_html,
            attachment_filename=f'{receipt_number}.pdf',
            attachment_bytes=receipt_artifact.pdf_bytes,
            from_email='hi@hispeedcity.com',
        )
        email_status = email_result.status
        email_sent_at = email_result.sent_at
        email_provider_message_id = email_result.provider_message_id
    except Exception as exc:
        email_error_message = str(exc)

    approved_at = datetime.now(timezone.utc)
    result = await db.renewals.find_one_and_update(
        {'renewalReference': renewal_reference},
        {
            '$set': {
                'status': STATUS_APPROVED,
                'receiptInfo': receipt_info,
                'approvedBy': username,
                'approvedAt': approved_at,
                'emailStatus': email_status,
                'emailSentAt': email_sent_at,
                'emailErrorMessage': email_error_message,
                'emailProviderMessageId': email_provider_message_id,
                'updatedAt': approved_at,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        raise HTTPException(status_code=404, detail='Renewal request not found')

    return {
        'message': 'Renewal approved successfully',
        'receiptPdfGenerated': True,
        'receiptPdfPath': str(receipt_artifact.pdf_path),
        'receiptPdfSizeBytes': len(receipt_artifact.pdf_bytes),
        'emailStatus': email_status,
        'emailSentAt': email_sent_at,
        'emailErrorMessage': email_error_message,
        'renewal': serialize_doc(result),
    }


@api_router.get('/renewals/reference/{renewal_reference}')
async def get_public_renewal_by_reference(renewal_reference: str):
    renewal = await db.renewals.find_one({'renewalReference': renewal_reference})
    if not renewal:
        raise HTTPException(status_code=404, detail='Renewal request not found')
    return serialize_doc(renewal)

@api_router.post('/applications', response_model=ApplicationCreateResponse)
async def create_application(
    applicationData: str = Form(...),
    receipt: Optional[UploadFile] = File(None),
):
    import json
    import re

    try:
        payload = json.loads(applicationData)
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid application data')

    # Application type determines whether payment/receipt is required
    application_type = (payload.get('applicationType') or 'registration').strip().lower()
    if application_type not in {'registration', 'deregistration', 'edit_remove'}:
        application_type = 'registration'
    payment_required = application_type == 'registration'

    vehicles = payload.get('vehicles') or []
    if not vehicles:
        raise HTTPException(status_code=400, detail='At least one vehicle is required')

    first_vehicle = vehicles[0]
    if not all([
        payload.get('fullName'), payload.get('phoneNumber'), payload.get('companyName'),
        first_vehicle.get('vehicleNumber'), first_vehicle.get('vehicleModel'), first_vehicle.get('vehicleType'), first_vehicle.get('vehicleColor'),
        payload.get('parkingType'), payload.get('subscriptionPeriod')
    ]):
        raise HTTPException(status_code=400, detail='Missing required fields')

    # Email validation
    email_raw = payload.get('email')
    if not email_raw or not str(email_raw).strip():
        raise HTTPException(status_code=400, detail='Customer email is required')
    email_clean = str(email_raw).strip()
    email_regex = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    if not email_regex.match(email_clean):
        raise HTTPException(status_code=400, detail='Invalid email format')

    # Remarks are required for edit_remove
    remarks_raw = payload.get('remarks') or ''
    remarks_clean = str(remarks_raw).strip()
    if application_type == 'edit_remove' and not remarks_clean:
        raise HTTPException(status_code=400, detail='Remarks / Notes are required for Edit / Remove Vehicle requests')

    parking_key = parking_type_to_key(payload.get('parkingType'))
    if not parking_key:
        raise HTTPException(status_code=400, detail='Invalid parking type selected')

    parking_availability_map = await get_parking_availability_map()
    parking_record = parking_availability_map.get(parking_key)
    if not parking_record:
        raise HTTPException(status_code=400, detail='Invalid parking type selected')
    if not parking_record.get('available', True):
        raise HTTPException(status_code=400, detail=f'{parking_type_to_label(payload.get("parkingType"))} is sold out. Please choose another parking type.')

    # Receipt is only required for paid (registration) applications
    receipt_url = ''
    if payment_required:
        if receipt is None:
            raise HTTPException(status_code=400, detail='Payment receipt is required')
        receipt_url = await upload_receipt(receipt)

    year = datetime.now(timezone.utc).year
    counter_id = f'applications-{year}'
    counter = await db.counters.find_one_and_update(
        {'_id': counter_id},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True,
    )
    if not counter:
        counter = {'seq': 1}
    sequence = counter.get('seq', 1)
    reference_number = f'SP-{year}-{sequence:06d}'

    total_amount = payload.get('totalAmount')
    if not isinstance(total_amount, (int, float)) or total_amount <= 0:
        total_amount = calculate_total_amount(payload.get('parkingType', ''), payload.get('subscriptionPeriod', ''), len(vehicles))

    document = {
        'referenceNumber': reference_number,
        'applicationType': application_type,
        'paymentRequired': payment_required,
        'remarks': remarks_clean,
        'fullName': payload.get('fullName'),
        'phoneNumber': payload.get('phoneNumber'),
        'email': email_clean,
        'companyName': payload.get('companyName'),
        'staffId': (payload.get('staffId') or '').strip(),
        'vehicleNumber': first_vehicle.get('vehicleNumber'),
        'vehicleModel': first_vehicle.get('vehicleModel'),
        'vehicleType': first_vehicle.get('vehicleType'),
        'vehicleColor': first_vehicle.get('vehicleColor'),
        'vehicles': vehicles,
        'parkingType': payload.get('parkingType'),
        'subscriptionPeriod': payload.get('subscriptionPeriod'),
        'totalAmount': total_amount,
        'receiptUrl': receipt_url,
        'status': STATUS_PENDING,
        'submittedAt': datetime.now(timezone.utc),
        'updatedAt': datetime.now(timezone.utc),
    }

    await db.applications.insert_one(document)
    return ApplicationCreateResponse(
        message='Application submitted successfully',
        referenceNumber=reference_number,
        status=STATUS_PENDING,
        submittedAt=document['submittedAt'],
    )


@api_router.get('/applications/reference/{reference_number}')
async def get_application_by_reference(reference_number: str):
    application = await db.applications.find_one({'referenceNumber': reference_number})
    if not application:
        raise HTTPException(status_code=404, detail='Application not found')
    return to_application_response(application)


@app.on_event('startup')
async def startup_event():
    try:
        admin_count = await db.admins.count_documents({})
        if admin_count == 0:
            await db.admins.insert_one({
                'username': ADMIN_USERNAME,
                'passwordHash': hash_password(ADMIN_PASSWORD).decode('utf-8'),
                'createdAt': datetime.now(timezone.utc),
            })
        await seed_default_parking_settings()
    except Exception as exc:
        print(f'Application startup warning: database initialization skipped: {exc}')


@app.on_event('shutdown')
async def shutdown_event():
    client.close()


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ['*'] else ['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

# ======================================================================
# HELPLINE CASE MANAGEMENT (NEW)  -  Problem Log, Car Clamping, Accident, Oil Leak
#
# WHERE TO PASTE: in backend-python-old/server.py (the Python backend that has api_router),
#   directly ABOVE the line      app.include_router(api_router)
#   (that line exists only once, at the very bottom of the file). Paste this WHOLE block.
#
# It only ADDS code. It re-uses what the portal already has, the same way the portal does:
#   api_router, db, require_admin (admin login), db.counters + ReturnDocument (reference numbers like SP-2026-000095),
#   cloudinary.uploader (file upload like the payment receipts), run_in_threadpool, UploadFile / File / Form.
# New MongoDB collections (created automatically):
#   helpline_logs, helpline_clamping, helpline_accidents, helpline_oilleaks, helpline_audit
# There is NO delete route for any of them. Audit records cannot be edited either.
# ======================================================================
import json as helpline_json
import re as helpline_re
from datetime import timedelta as helpline_timedelta

# --- case types: each one has its OWN case number format  PREFIX-YEAR-000001 -------------------------------
HELPLINE_KINDS = {
    'logs':      {'coll': 'helpline_logs',      'prefix': 'HL', 'type': 'HELPLINE CALL'},
    'clamping':  {'coll': 'helpline_clamping',  'prefix': 'WC', 'type': 'WHEEL CLAMPING'},
    'accidents': {'coll': 'helpline_accidents', 'prefix': 'AC', 'type': 'ACCIDENT'},
    'oilleaks':  {'coll': 'helpline_oilleaks',  'prefix': 'OL', 'type': 'OIL LEAK'},
}
# photo proof labels per case type (the first one is the default)
HELPLINE_PHOTO_LABELS = {
    'clamping':  ['CLAMPED', 'RELEASED'],
    'accidents': ['ACCIDENT SCENE', 'VEHICLE DAMAGE', 'OTHER'],
    'oilleaks':  ['OIL LEAK', 'AFTER CLEANUP', 'OTHER'],
}
HELPLINE_STATIONS = ['ENTRY 101', 'ENTRY 102', 'EXIT 201', 'EXIT 202']
HELPLINE_TYPES = ['Season', 'Hourly']
HELPLINE_UPPER_FIELDS = ['plate', 'entry', 'exit', 'station', 'reason', 'solution', 'remarks']
CLAMP_STATUSES = ['CLAMPED', 'RELEASED']
CLAMP_UPPER_FIELDS = ['plate', 'location', 'reason', 'clampedBy', 'receiptNo', 'releasedBy', 'remarks']
HELPLINE_MIN_DATE = '2024-01-01'          # nothing older than the first logbook month
HELPLINE_MAX_OVERNIGHT_DAYS = 31          # longest stay accepted when an exit date is entered
HELPLINE_MAX_PHOTO_BYTES = 8 * 1024 * 1024   # 8 MB per photo
HELPLINE_MAX_PHOTOS_PER_REQUEST = 4
HELPLINE_MAX_PHOTOS_PER_CASE = 30
_helpline_indexes_ready = False


def helpline_coll(kind: str):
    return db[HELPLINE_KINDS[kind]['coll']]


async def ensure_helpline_indexes():
    """Create MongoDB indexes once (safe to repeat). Never blocks a request if it fails."""
    global _helpline_indexes_ready
    if _helpline_indexes_ready:
        return
    for kind in HELPLINE_KINDS:
        coll = helpline_coll(kind)
        for keys, opts in (('logId', {'unique': True}), ('caseNo', {'unique': True, 'sparse': True}), ('plate', {}), ([('date', -1)], {})):
            try:
                await coll.create_index(keys, **opts)
            except Exception as exc:
                print(f'Helpline index warning ({kind}): {exc}')
    for keys, opts in (('auditId', {'unique': True}), ([('kind', 1), ('logId', 1), ('changedAt', -1)], {}), ([('changedAt', -1)], {})):
        try:
            await db.helpline_audit.create_index(keys, **opts)
        except Exception as exc:
            print(f'Helpline audit index warning: {exc}')
    _helpline_indexes_ready = True


# ---------------------------- CASE NUMBERS (same method as SP-2026-000095 / RN-2026-000001) ----------------------------
async def helpline_next_case_numbers(kind: str, year: int, count: int = 1) -> list:
    prefix = HELPLINE_KINDS[kind]['prefix']
    counter = await db.counters.find_one_and_update(
        {'_id': f'helpline-{prefix}-{year}'},
        {'$inc': {'seq': count}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    last = int((counter or {}).get('seq', count))
    return [f'{prefix}-{year}-{n:06d}' for n in range(last - count + 1, last + 1)]


# ---------------------------- VALIDATION HELPERS ----------------------------
def helpline_check_date(value: str, label: str, limit_range: bool = True) -> str:
    """Date must be a real YYYY-MM-DD date, not before Jan 2024 and not in the future."""
    value = str(value or '').strip()
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail=f'{label} must be a real date (YYYY-MM-DD)')
    if limit_range:
        if value < HELPLINE_MIN_DATE:
            raise HTTPException(status_code=400, detail=f'{label} cannot be before 01/01/2024')
        latest = (datetime.now(timezone.utc) + helpline_timedelta(days=1)).strftime('%Y-%m-%d')   # +1 day covers Malaysia time
        if value > latest:
            raise HTTPException(status_code=400, detail=f'{label} cannot be in the future')
    return value


def helpline_norm_time(value, label: str, required: bool = False) -> str:
    """Accepts 14:28, 8:15, 8.15, 8:15 AM, 2:28 PM and stores 24-hour HH:MM."""
    raw = str(value or '').strip().upper()
    if not raw:
        if required:
            raise HTTPException(status_code=400, detail=f'{label} is required')
        return ''
    match = helpline_re.fullmatch(r'(\d{1,2})[:.](\d{2})\s*(AM|PM)?', raw)
    if not match:
        raise HTTPException(status_code=400, detail=f'{label} must be a time like 14:28 (24-hour)')
    hour, minute, ampm = int(match.group(1)), int(match.group(2)), match.group(3)
    if ampm:
        if not 1 <= hour <= 12:
            raise HTTPException(status_code=400, detail=f'{label} is not a valid time')
        hour = (hour % 12) + (12 if ampm == 'PM' else 0)
    if hour > 23 or minute > 59:
        raise HTTPException(status_code=400, detail=f'{label} is not a valid time')
    return f'{hour:02d}:{minute:02d}'


def helpline_norm_plate(value) -> str:
    plate = helpline_re.sub(r'\s+', ' ', str(value or '').strip().upper())
    if not helpline_re.fullmatch(r'[A-Z0-9][A-Z0-9 ]{1,11}', plate):
        raise HTTPException(status_code=400, detail='Car plate must be 2 to 12 letters or numbers, no symbols (example: JWN 1078)')
    return plate


def helpline_need(data: Dict[str, Any], rules) -> None:
    for key, label in rules:
        if not data.get(key):
            raise HTTPException(status_code=400, detail=f'{label} is required')


def helpline_limit_text(data: Dict[str, Any]) -> None:
    for key, value in data.items():
        if isinstance(value, str) and len(value) > 2000:
            raise HTTPException(status_code=400, detail=f'{key} is too long (maximum 2000 characters)')


# ---------------------------- AUDIT TRAIL ----------------------------
# Every create, edit, photo and import is written to helpline_audit: who, when, and what changed (old value -> new value).
# Audit records can never be edited or deleted (no route exists for that).
def helpline_text(value) -> str:
    return '' if value is None else str(value)


def helpline_diff(old: Dict[str, Any], new: Dict[str, Any], fields) -> list:
    return [{'field': f, 'from': helpline_text(old.get(f)), 'to': helpline_text(new.get(f))}
            for f in fields if helpline_text(old.get(f)) != helpline_text(new.get(f))]


async def helpline_audit_write(kind: str, log_id: str, plate: str, action: str, username: str, changes=None, note: str = '', case_no: str = ''):
    await db.helpline_audit.insert_one({
        'auditId': str(uuid.uuid4()), 'kind': kind, 'logId': log_id, 'caseNo': case_no, 'plate': plate, 'action': action,
        'changedBy': username, 'changedAt': datetime.now(timezone.utc).isoformat(), 'changes': changes or [], 'note': note,
    })


@api_router.get('/admin/helpline-audit/{kind}/{log_id}')
async def helpline_audit_for_record(kind: str, log_id: str, _: str = Depends(require_admin)):
    if kind not in HELPLINE_KINDS:
        raise HTTPException(status_code=404, detail='Unknown audit type')
    docs = await db.helpline_audit.find({'kind': kind, 'logId': log_id}, {'_id': 0}).sort([('changedAt', -1)]).to_list(1000)
    return {'history': docs}


@api_router.get('/admin/helpline-audit')
async def helpline_audit_recent(limit: int = 200, _: str = Depends(require_admin)):
    docs = await db.helpline_audit.find({}, {'_id': 0}).sort([('changedAt', -1)]).to_list(max(1, min(limit, 2000)))
    return {'history': docs}


# ---------------------------- PHOTO PROOF (Cloudinary, same way as the payment receipts) ----------------------------
def helpline_sniff_image(data: bytes) -> str:
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return ''


async def helpline_read_photos(files) -> list:
    """Read and check uploaded photos (JPG, PNG or WEBP, up to 8 MB each, up to 4 per request)."""
    files = [f for f in (files or []) if f is not None and getattr(f, 'filename', '')]
    if len(files) > HELPLINE_MAX_PHOTOS_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f'Upload at most {HELPLINE_MAX_PHOTOS_PER_REQUEST} photos at a time')
    out = []
    for f in files:
        contents = await f.read()
        if not contents:
            raise HTTPException(status_code=400, detail='A photo file is empty')
        if len(contents) > HELPLINE_MAX_PHOTO_BYTES:
            raise HTTPException(status_code=400, detail='A photo is larger than 8 MB')
        content_type = helpline_sniff_image(contents)
        if not content_type:
            raise HTTPException(status_code=400, detail='Only JPG, PNG or WEBP photos are accepted')
        name = helpline_re.sub(r'[^A-Za-z0-9._ -]', '_', os.path.basename(f.filename))[:80] or 'photo'
        out.append({'bytes': contents, 'filename': name, 'contentType': content_type})
    return out


def helpline_pick_label(kind: str, label) -> str:
    allowed = HELPLINE_PHOTO_LABELS.get(kind, [])
    label = str(label or '').strip().upper() or (allowed[0] if allowed else '')
    if label not in allowed:
        raise HTTPException(status_code=400, detail='Photo type must be one of: ' + ', '.join(allowed))
    return label


async def helpline_upload_photo(kind: str, photo: Dict[str, Any], label: str, username: str) -> Dict[str, Any]:
    prefix = HELPLINE_KINDS[kind]['prefix']
    try:
        result = await run_in_threadpool(
            lambda: cloudinary.uploader.upload(
                photo['bytes'],
                resource_type='image',
                folder=f'hispeedcity/helpline/{prefix}',
                public_id=f'{prefix}-{uuid.uuid4().hex}',
            )
        )
    except Exception as exc:
        print(f'Helpline photo upload failed: {exc}')
        raise HTTPException(status_code=502, detail='Photo upload failed. Please try again.')
    return {
        'photoId': str(uuid.uuid4()), 'label': label, 'url': result['secure_url'], 'publicId': result.get('public_id', ''),
        'filename': photo['filename'], 'size': len(photo['bytes']), 'contentType': photo['contentType'],
        'uploadedAt': datetime.now(timezone.utc).isoformat(), 'uploadedBy': username,
    }


def helpline_parse_record(model, raw: str):
    try:
        return model.model_validate(helpline_json.loads(raw))
    except Exception:
        raise HTTPException(status_code=400, detail='The record data is not valid')


# ---------------------------- PROBLEM LOG (case type HL) ----------------------------
HELPLINE_AUDIT_FIELDS = ['date', 'plate', 'entry', 'exitDate', 'exit', 'station', 'type', 'reason', 'solution', 'remarks']


class HelplineLogPayload(BaseModel):
    date: str
    plate: str
    entry: Optional[str] = ''
    exitDate: Optional[str] = ''      # only filled when the car stayed overnight
    exit: Optional[str] = ''
    station: str
    reason: str
    solution: Optional[str] = ''
    type: str
    remarks: Optional[str] = ''


def clean_helpline_log(payload: HelplineLogPayload, legacy: bool = False, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = payload.model_dump()
    for key in HELPLINE_UPPER_FIELDS:
        data[key] = str(data.get(key) or '').strip().upper()          # always CAPITAL
    data['type'] = str(data.get('type') or '').strip().capitalize()
    data['exitDate'] = str(data.get('exitDate') or '').strip()
    helpline_limit_text(data)
    if legacy:
        # Old Excel records may be incomplete or oddly written. Only a real date and a plate are needed.
        data['date'] = helpline_check_date(data['date'], 'Date', limit_range=False)
        data['plate'] = helpline_re.sub(r'\s+', ' ', data['plate'])
        if not data['plate']:
            raise HTTPException(status_code=400, detail='Car plate is required')
        if data['type'] not in HELPLINE_TYPES and data['type'] != '':
            raise HTTPException(status_code=400, detail='Type of parker must be Season or Hourly')
        return data

    existing = existing or {}
    same = lambda key: bool(existing) and data[key] == helpline_text(existing.get(key))   # unchanged value on an old record is not re-checked
    if not same('date'):
        data['date'] = helpline_check_date(data['date'], 'Date')
    if not same('plate'):
        data['plate'] = helpline_norm_plate(data['plate'])
    for key, label in (('reason', 'Problem'), ('solution', 'Solution')):
        if not data[key] and (not existing or existing.get(key)):
            raise HTTPException(status_code=400, detail=f'{label} is required')
    if data['entry'] and not same('entry'):
        data['entry'] = helpline_norm_time(data['entry'], 'Entry time')
    if data['exit'] and not same('exit'):
        data['exit'] = helpline_norm_time(data['exit'], 'Exit time')
    if data['exitDate']:
        data['exitDate'] = helpline_check_date(data['exitDate'], 'Exit date')
        if data['exitDate'] < data['date']:
            raise HTTPException(status_code=400, detail='Exit date cannot be before the entry date')
        days = (datetime.strptime(data['exitDate'], '%Y-%m-%d') - datetime.strptime(data['date'], '%Y-%m-%d')).days
        if days > HELPLINE_MAX_OVERNIGHT_DAYS:
            raise HTTPException(status_code=400, detail=f'Exit date is more than {HELPLINE_MAX_OVERNIGHT_DAYS} days after the entry date')
        if not data['exit']:
            raise HTTPException(status_code=400, detail='Exit time is required when an exit date is entered')
    overnight = bool(data['exitDate']) and data['exitDate'] > data['date']
    if data['entry'] and data['exit'] and not overnight and data['exit'] < data['entry'] and (not same('entry') or not same('exit')):
        raise HTTPException(status_code=400, detail='Exit time is earlier than entry time. If the car stayed overnight, enter the Exit Date.')
    if data['type'] not in HELPLINE_TYPES and not (existing and not existing.get('type') and data['type'] == ''):
        raise HTTPException(status_code=400, detail='Type of parker must be Season or Hourly')
    if not (data['station'] in HELPLINE_STATIONS or (existing and data['station'] == existing.get('station', ''))):
        raise HTTPException(status_code=400, detail='Station must be ENTRY 101, ENTRY 102, EXIT 201 or EXIT 202')
    return data


@api_router.get('/admin/helpline-logs')
async def list_helpline_logs(_: str = Depends(require_admin)):
    await ensure_helpline_indexes()
    docs = await db.helpline_logs.find({}, {'_id': 0}).sort([('date', -1), ('createdAt', -1)]).to_list(10000)
    return {'logs': docs}


@api_router.post('/admin/helpline-logs')
async def create_helpline_log(payload: HelplineLogPayload, username: str = Depends(require_admin)):
    await ensure_helpline_indexes()
    data = clean_helpline_log(payload)
    if await db.helpline_logs.count_documents({'plate': data['plate'], 'date': data['date'], 'entry': data['entry'], 'station': data['station']}) > 0:
        raise HTTPException(status_code=409, detail='This record already exists (same plate, date, entry time and station). Use Edit instead.')
    case_no = (await helpline_next_case_numbers('logs', int(data['date'][:4])))[0]
    now = datetime.now(timezone.utc).isoformat()
    data.update({'logId': str(uuid.uuid4()), 'caseNo': case_no, 'caseType': HELPLINE_KINDS['logs']['type'],
                 'createdAt': now, 'createdBy': username, 'updatedAt': now, 'updatedBy': username})
    await db.helpline_logs.insert_one(dict(data))
    await helpline_audit_write('logs', data['logId'], data['plate'], 'CREATE', username, note='RECORD CREATED', case_no=case_no)
    return {'message': f'Case {case_no} saved', 'log': data}


@api_router.put('/admin/helpline-logs/{log_id}')
async def update_helpline_log(log_id: str, payload: HelplineLogPayload, username: str = Depends(require_admin)):
    existing = await db.helpline_logs.find_one({'logId': log_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail='Log not found')
    data = clean_helpline_log(payload, existing=existing)
    changes = helpline_diff(existing, data, HELPLINE_AUDIT_FIELDS)
    if not changes:
        return {'message': 'No changes', 'log': existing}
    data.update({'updatedAt': datetime.now(timezone.utc).isoformat(), 'updatedBy': username})
    await db.helpline_logs.update_one({'logId': log_id}, {'$set': data})
    await helpline_audit_write('logs', log_id, data['plate'], 'UPDATE', username, changes, case_no=existing.get('caseNo', ''))
    return {'message': 'Log updated', 'log': {**existing, **data}}


@api_router.post('/admin/helpline-logs/import-legacy')
async def import_legacy_helpline_logs(payloads: list[HelplineLogPayload], username: str = Depends(require_admin)):
    # One-time import of the old Excel logbook. Refused if any record already exists (no duplicates).
    # Every old record also gets its own case number (HL-YEAR-000001 ...), oldest first.
    await ensure_helpline_indexes()
    if await db.helpline_logs.count_documents({}) > 0:
        raise HTTPException(status_code=409, detail='Logbook already has records. Import skipped.')
    now = datetime.now(timezone.utc).isoformat()
    docs = []
    for item in payloads:
        data = clean_helpline_log(item, legacy=True)
        data.update({'logId': str(uuid.uuid4()), 'caseType': HELPLINE_KINDS['logs']['type'], 'createdAt': now, 'createdBy': username,
                     'updatedAt': now, 'updatedBy': username, 'legacy': True})
        docs.append(data)
    by_year: Dict[int, list] = {}
    for d in sorted(docs, key=lambda x: x['date']):
        by_year.setdefault(int(d['date'][:4]), []).append(d)
    for year, group in sorted(by_year.items()):
        for d, number in zip(group, await helpline_next_case_numbers('logs', year, len(group))):
            d['caseNo'] = number
    if docs:
        await db.helpline_logs.insert_many([dict(d) for d in docs])
        await helpline_audit_write('logs', '*', '', 'IMPORT', username, note=f'{len(docs)} OLD LOGBOOK RECORDS IMPORTED')
    return {'message': f'{len(docs)} old records imported', 'count': len(docs)}


# ---------------------------- SAME ROUTES FOR CLAMPING, ACCIDENT AND OIL LEAK ----------------------------
def helpline_register_case_routes(kind, path, PayloadModel, clean_fn, audit_fields, dup_fields, required_photo_label=None, create_check=None, update_check=None):
    """Creates: list, create (with photos), edit, add photos.  No delete route is created."""

    @api_router.get(f'/admin/helpline-{path}', name=f'helpline_list_{kind}')
    async def list_cases(_: str = Depends(require_admin)):
        await ensure_helpline_indexes()
        docs = await helpline_coll(kind).find({}, {'_id': 0}).sort([('date', -1), ('createdAt', -1)]).to_list(10000)
        return {'logs': docs}

    @api_router.post(f'/admin/helpline-{path}', name=f'helpline_create_{kind}')
    async def create_case(record: str = Form(...), photos: List[UploadFile] = File(default=[]), photoLabel: Optional[str] = Form(None), username: str = Depends(require_admin)):
        await ensure_helpline_indexes()
        data = clean_fn(helpline_parse_record(PayloadModel, record))
        if create_check:
            create_check(data)
        picked = await helpline_read_photos(photos)
        if required_photo_label and not picked:
            raise HTTPException(status_code=400, detail='A photo showing the car plate is required to save this case')
        label = helpline_pick_label(kind, photoLabel if not required_photo_label else required_photo_label) if picked else ''
        if await helpline_coll(kind).count_documents({k: data[k] for k in dup_fields}) > 0:
            raise HTTPException(status_code=409, detail='This case already exists (same plate, date and time). Use Edit instead.')
        uploaded = [await helpline_upload_photo(kind, p, label, username) for p in picked]
        case_no = (await helpline_next_case_numbers(kind, int(data['date'][:4])))[0]
        now = datetime.now(timezone.utc).isoformat()
        data.update({'logId': str(uuid.uuid4()), 'caseNo': case_no, 'caseType': HELPLINE_KINDS[kind]['type'], 'photos': uploaded,
                     'createdAt': now, 'createdBy': username, 'updatedAt': now, 'updatedBy': username})
        await helpline_coll(kind).insert_one(dict(data))
        await helpline_audit_write(kind, data['logId'], data['plate'], 'CREATE', username, note='RECORD CREATED' + (f' WITH {len(uploaded)} PHOTO(S)' if uploaded else ''), case_no=case_no)
        return {'message': f'Case {case_no} saved', 'log': data}

    async def update_case(log_id: str, payload: PayloadModel, username: str = Depends(require_admin)):
        existing = await helpline_coll(kind).find_one({'logId': log_id}, {'_id': 0})
        if not existing:
            raise HTTPException(status_code=404, detail='Case not found')
        data = clean_fn(payload)
        if update_check:
            update_check(existing, data)
        changes = helpline_diff(existing, data, audit_fields)
        if not changes:
            return {'message': 'No changes', 'log': existing}
        data.update({'updatedAt': datetime.now(timezone.utc).isoformat(), 'updatedBy': username})
        await helpline_coll(kind).update_one({'logId': log_id}, {'$set': data})
        await helpline_audit_write(kind, log_id, data['plate'], 'UPDATE', username, changes, case_no=existing.get('caseNo', ''))
        return {'message': 'Case updated', 'log': {**existing, **data}}

    # server.py uses 'from __future__ import annotations' (type hints are text), so give FastAPI the real model class here
    update_case.__annotations__['payload'] = PayloadModel
    api_router.add_api_route(f'/admin/helpline-{path}/{{log_id}}', update_case, methods=['PUT'], name=f'helpline_update_{kind}')

    @api_router.post(f'/admin/helpline-{path}/{{log_id}}/photos', name=f'helpline_photos_{kind}')
    async def add_photos(log_id: str, label: str = Form(...), photos: List[UploadFile] = File(...), username: str = Depends(require_admin)):
        existing = await helpline_coll(kind).find_one({'logId': log_id}, {'_id': 0})
        if not existing:
            raise HTTPException(status_code=404, detail='Case not found')
        label = helpline_pick_label(kind, label)
        picked = await helpline_read_photos(photos)
        if not picked:
            raise HTTPException(status_code=400, detail='Choose a photo to upload')
        if len(existing.get('photos', [])) + len(picked) > HELPLINE_MAX_PHOTOS_PER_CASE:
            raise HTTPException(status_code=400, detail=f'A case can have at most {HELPLINE_MAX_PHOTOS_PER_CASE} photos')
        uploaded = [await helpline_upload_photo(kind, p, label, username) for p in picked]
        now = datetime.now(timezone.utc).isoformat()
        await helpline_coll(kind).update_one({'logId': log_id}, {'$push': {'photos': {'$each': uploaded}}, '$set': {'updatedAt': now, 'updatedBy': username}})
        await helpline_audit_write(kind, log_id, existing.get('plate', ''), 'PHOTO', username,
                                   [{'field': 'photo', 'from': '', 'to': f"{label}: {u['filename']}"} for u in uploaded],
                                   note=f'{len(uploaded)} PHOTO(S) ADDED: {label}', case_no=existing.get('caseNo', ''))
        return {'message': f'{len(uploaded)} photo(s) added', 'photos': uploaded}


# ---------------------------- CAR CLAMPING (case type WC) ----------------------------
CLAMP_AUDIT_FIELDS = ['date', 'clampTime', 'plate', 'type', 'location', 'reason', 'clampedBy', 'fineAmount', 'receiptNo', 'status', 'releaseDate', 'releaseTime', 'releasedBy', 'remarks']


class ClampPayload(BaseModel):
    date: str
    plate: str
    location: str
    clampTime: str
    type: str
    reason: str
    clampedBy: str
    status: str = 'CLAMPED'
    fineAmount: Optional[float] = None
    receiptNo: Optional[str] = ''
    releaseDate: Optional[str] = ''
    releaseTime: Optional[str] = ''
    releasedBy: Optional[str] = ''
    remarks: Optional[str] = ''


def clean_clamp(payload: ClampPayload) -> Dict[str, Any]:
    data = payload.model_dump()
    for key in CLAMP_UPPER_FIELDS:
        data[key] = str(data.get(key) or '').strip().upper()
    data['status'] = str(data.get('status') or '').strip().upper()
    data['type'] = str(data.get('type') or '').strip().capitalize()
    helpline_limit_text(data)
    data['date'] = helpline_check_date(data['date'], 'Clamp date')
    data['plate'] = helpline_norm_plate(data['plate'])
    data['clampTime'] = helpline_norm_time(data.get('clampTime'), 'Clamp time', required=True)
    helpline_need(data, (('location', 'Location'), ('reason', 'Reason'), ('clampedBy', 'Clamped by')))
    if data['type'] not in HELPLINE_TYPES:
        raise HTTPException(status_code=400, detail='Type of parker must be Season or Hourly')
    if data['status'] not in CLAMP_STATUSES:
        raise HTTPException(status_code=400, detail='Status must be CLAMPED or RELEASED')
    fine = data.get('fineAmount')
    if fine is not None:
        if fine < 0 or fine > 100000:
            raise HTTPException(status_code=400, detail='Fine amount must be between 0 and 100000')
        data['fineAmount'] = round(float(fine), 2)
    if data['status'] == 'RELEASED':
        data['releaseDate'] = helpline_check_date(data.get('releaseDate'), 'Release date')
        data['releaseTime'] = helpline_norm_time(data.get('releaseTime'), 'Release time', required=True)
        if not data['releasedBy']:
            raise HTTPException(status_code=400, detail='Released by is required when status is RELEASED')
        if (data['releaseDate'], data['releaseTime']) < (data['date'], data['clampTime']):
            raise HTTPException(status_code=400, detail='Release date and time cannot be before the clamp date and time')
    else:
        data['releaseDate'] = ''
        data['releaseTime'] = ''
        data['releasedBy'] = ''
    return data


def clamp_create_check(data: Dict[str, Any]) -> None:
    if data['status'] != 'CLAMPED':
        raise HTTPException(status_code=400, detail='A new clamping case starts as CLAMPED. Release it later with the release photo.')


def clamp_update_check(existing: Dict[str, Any], data: Dict[str, Any]) -> None:
    if data['status'] == 'RELEASED' and not any(p.get('label') == 'RELEASED' for p in existing.get('photos', [])):
        raise HTTPException(status_code=400, detail='Upload the photo of the released car before releasing the vehicle')


helpline_register_case_routes('clamping', 'clamping', ClampPayload, clean_clamp, CLAMP_AUDIT_FIELDS, ['plate', 'date', 'clampTime'],
                              required_photo_label='CLAMPED', create_check=clamp_create_check, update_check=clamp_update_check)


# ---------------------------- ACCIDENT (case type AC) ----------------------------
ACCIDENT_UPPER_FIELDS = ['plate', 'otherPlate', 'location', 'description', 'injuries', 'policeReportNo', 'insuranceRef', 'reportedBy', 'remarks']
ACCIDENT_AUDIT_FIELDS = ['date', 'time', 'plate', 'otherPlate', 'location', 'description', 'injuries', 'policeReportNo', 'insuranceRef', 'reportedBy', 'remarks']


class AccidentPayload(BaseModel):
    date: str
    time: str
    plate: str
    otherPlate: Optional[str] = ''
    location: str
    description: str
    injuries: str = 'NO'
    policeReportNo: Optional[str] = ''
    insuranceRef: Optional[str] = ''
    reportedBy: str
    remarks: Optional[str] = ''


def clean_accident(payload: AccidentPayload) -> Dict[str, Any]:
    data = payload.model_dump()
    for key in ACCIDENT_UPPER_FIELDS:
        data[key] = str(data.get(key) or '').strip().upper()
    helpline_limit_text(data)
    data['date'] = helpline_check_date(data['date'], 'Accident date')
    data['time'] = helpline_norm_time(data.get('time'), 'Accident time', required=True)
    data['plate'] = helpline_norm_plate(data['plate'])
    if data['otherPlate']:
        data['otherPlate'] = helpline_norm_plate(data['otherPlate'])
    helpline_need(data, (('location', 'Location'), ('description', 'Description'), ('reportedBy', 'Reported by')))
    if data['injuries'] not in ('NO', 'YES'):
        raise HTTPException(status_code=400, detail='Injuries must be NO or YES')
    return data


helpline_register_case_routes('accidents', 'accidents', AccidentPayload, clean_accident, ACCIDENT_AUDIT_FIELDS, ['plate', 'date', 'time'])


# ---------------------------- OIL LEAK (case type OL) ----------------------------
OILLEAK_UPPER_FIELDS = ['plate', 'location', 'description', 'actionTaken', 'cleanedBy', 'reportedBy', 'remarks']
OILLEAK_AUDIT_FIELDS = ['date', 'time', 'plate', 'location', 'description', 'actionTaken', 'cleanedBy', 'reportedBy', 'remarks']


class OilLeakPayload(BaseModel):
    date: str
    time: str
    plate: str                       # type UNKNOWN if the vehicle is not known
    location: str
    description: str
    actionTaken: str
    cleanedBy: Optional[str] = ''
    reportedBy: str
    remarks: Optional[str] = ''


def clean_oilleak(payload: OilLeakPayload) -> Dict[str, Any]:
    data = payload.model_dump()
    for key in OILLEAK_UPPER_FIELDS:
        data[key] = str(data.get(key) or '').strip().upper()
    helpline_limit_text(data)
    data['date'] = helpline_check_date(data['date'], 'Oil leak date')
    data['time'] = helpline_norm_time(data.get('time'), 'Oil leak time', required=True)
    data['plate'] = helpline_norm_plate(data['plate'])
    helpline_need(data, (('location', 'Location'), ('description', 'Description'), ('actionTaken', 'Action taken'), ('reportedBy', 'Reported by')))
    return data


helpline_register_case_routes('oilleaks', 'oil-leaks', OilLeakPayload, clean_oilleak, OILLEAK_AUDIT_FIELDS, ['plate', 'date', 'time'])
# ============================ END HELPLINE CASE MANAGEMENT ============================


# ============================ HISPEEDCITY AI ASSISTANT ============================
class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=128)


class AssistantChatResponse(BaseModel):
    answer: str
    intent: str
    confidence: float
    requires_plate: bool = False
    vehicle_plate: Optional[str] = None
    portal_status: Optional[str] = None


_assistant_bot = None
_assistant_sessions: dict[str, dict[str, Any]] = {}


def assistant_bot():
    global _assistant_bot
    if _assistant_bot is None:
        # Hostless builds the backend directory as the application root, so
        # backend modules are imported as top-level packages (chatbot, loaders,
        # models, etc.), not through a nonexistent `backend` parent package.
        from chatbot.chatbot import ChatBot
        _assistant_bot = ChatBot()
    return _assistant_bot


def assistant_plate_pattern(value: str) -> str:
    plate = re.sub(r'\s+', '', str(value or '').upper())
    return r'^\s*' + r'\s*'.join(re.escape(ch) for ch in plate) + r'\s*$'


def assistant_plates(record: dict[str, Any]) -> list[str]:
    vehicles = record.get('vehicles') or []
    plates = [str(v.get('vehicleNumber') or '').strip().upper() for v in vehicles if isinstance(v, dict)]
    if not plates and record.get('vehicleNumber'):
        plates = [str(record['vehicleNumber']).strip().upper()]
    raw = record.get('vehiclePlateNumbers') or []
    if isinstance(raw, dict):
        raw = [plate for values in raw.values() for plate in (values if isinstance(values, list) else [])]
    if isinstance(raw, list):
        plates.extend(str(plate or '').strip().upper() for plate in raw)
    return list(dict.fromkeys(p for p in plates if p))


def assistant_portal_record(record: dict[str, Any], plate: Optional[str] = None) -> dict[str, Any]:
    return {
        'found': True,
        'vehicle_plate': plate or (assistant_plates(record)[0] if assistant_plates(record) else ''),
        'vehicle_plates': assistant_plates(record),
        'customer_name': record.get('fullName') or record.get('customerName') or record.get('contactPerson') or '',
        'parking_type': record.get('parkingType') or record.get('renewalType') or 'Season Parking',
        'status': record.get('status') or 'Unknown',
        'validity_period': record.get('subscriptionPeriod') or record.get('renewalMonthNote') or 'as shown in your approval email',
        'payment_status': 'Paid' if record.get('receiptInfo') or record.get('receiptUrl') else 'Not shown',
        'reference_number': record.get('referenceNumber') or record.get('renewalReference') or '',
    }


@api_router.get('/parking/status/{vehicle_plate}')
async def assistant_parking_status(vehicle_plate: str):
    pattern = assistant_plate_pattern(vehicle_plate)
    query = {'$or': [
        {'vehicleNumber': {'$regex': pattern, '$options': 'i'}},
        {'vehicles.vehicleNumber': {'$regex': pattern, '$options': 'i'}},
        {'vehiclePlateNumbers': {'$regex': pattern, '$options': 'i'}},
        {'vehiclePlateNumbers.non_reserved': {'$regex': pattern, '$options': 'i'}},
        {'vehiclePlateNumbers.reserved': {'$regex': pattern, '$options': 'i'}},
        {'vehiclePlateNumbers.premium': {'$regex': pattern, '$options': 'i'}},
    ]}
    records = await db.applications.find(query, {'_id': 0}).sort('updatedAt', -1).to_list(100)
    renewals = await db.renewals.find(query, {'_id': 0}).sort('updatedAt', -1).to_list(100)
    records.extend(renewals)
    if not records:
        return {'found': False, 'vehicle_plate': vehicle_plate.upper()}
    record = next((r for r in records if str(r.get('status', '')).lower() in ('active', 'approved')), records[0])
    return assistant_portal_record(record, vehicle_plate.upper())


@api_router.get('/parking/status/reference/{reference_number}')
async def assistant_reference_status(reference_number: str):
    ref = reference_number.strip().upper()
    record = await db.applications.find_one({'referenceNumber': ref}, {'_id': 0})
    if not record:
        record = await db.renewals.find_one({'renewalReference': ref}, {'_id': 0})
    if not record:
        return {'found': False, 'reference_number': ref}
    return assistant_portal_record(record)


@api_router.post('/ai/chat', response_model=AssistantChatResponse)
async def assistant_chat(payload: AssistantChatRequest):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail='Message cannot be empty')
    session_id = (payload.session_id or str(uuid.uuid4()))[:128]
    context = _assistant_sessions.get(session_id, {})
    try:
        result = await run_in_threadpool(assistant_bot().ask, message, context)
    except Exception as exc:
        print(f'AI assistant request failed: {exc}')
        raise HTTPException(status_code=503, detail='The assistant is temporarily unavailable. Please try again.')
    if result.get('vehicle_plate'):
        context['vehicle_plate'] = result['vehicle_plate']
    if result.get('intent'):
        context['intent'] = result['intent']
    _assistant_sessions[session_id] = context
    if len(_assistant_sessions) > 5000:
        _assistant_sessions.clear()
    return AssistantChatResponse(
        answer=result.get('answer', 'Sorry, I could not find an answer.'),
        intent=result.get('intent', 'general'),
        confidence=float(result.get('confidence', 0.0)),
        requires_plate=bool(result.get('requires_plate', False)),
        vehicle_plate=result.get('vehicle_plate'),
        portal_status=result.get('portal_status'),
    )
# ============================ END HISPEEDCITY AI ASSISTANT ============================


app.include_router(api_router)
