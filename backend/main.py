import os
import uuid
import json
import logging
import traceback
from datetime import datetime
from typing import List, Optional
import phonenumbers
from phonenumbers import NumberParseException
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from dotenv import load_dotenv
import httpx
import gspread
from google.oauth2.service_account import Credentials
from twilio.twiml.voice_response import VoiceResponse
from gspread.exceptions import APIError
from time import sleep
 
# ─── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Load environment variables ────────────────────────────────────────────────
load_dotenv()
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
VAPI_BASE_URL = os.getenv("VAPI_BASE_URL", "https://api.vapi.ai")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

if not GOOGLE_SHEET_ID:
    raise Exception("Missing required environment variable: GOOGLE_SHEET_ID")
if not all([VAPI_API_KEY, VAPI_ASSISTANT_ID, VAPI_PHONE_NUMBER_ID, TWILIO_PHONE_NUMBER]):
    raise Exception("Missing required VAPI/Twilio environment variables")

credentials_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
creds = Credentials.from_service_account_info(credentials_info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
workbook = gc.open_by_key(GOOGLE_SHEET_ID)

# ─── Worksheet names and expected columns ──────────────────────────────────────
SHEET_COLUMNS = {
    "Menu Items": ["id", "name", "price", "description", "category", "created_at"],
    "FAQs": ["id", "question", "answer", "created_at"],
    "Orders": ["id", "timestamp", "phone", "name", "items", "total", "special_instructions", "status"],
    "Reservations": ["id", "timestamp", "phone", "name", "date", "time", "party_size", "special_requests", "status"],
    "Call Logs": ["id", "timestamp", "phone", "duration", "status", "intent", "transcription", "notes"]
}

def safe_append_row(ws, row):
    retries = 3
    for attempt in range(retries):
        try:
            ws.append_row(row)
            return
        except APIError as e:
            if attempt < retries - 1:
                logger.warning(f"APIError: {e}, retrying in 5 seconds...")
                sleep(5)
            else:
                raise
def ensure_sheets_exist():
    existing = [ws.title for ws in workbook.worksheets()]
    for name, headers in SHEET_COLUMNS.items():
        try:
            if name not in existing:
                ws = workbook.add_worksheet(title=name, rows="1000", cols=len(headers))
                safe_append_row(ws, headers)
                ws.format("A1:Z1", {
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                    "textFormat": {"bold": True}
                })
                ws.freeze(rows=1)
                logger.info(f"Created worksheet: {name}")
            else:
                ws = workbook.worksheet(name)
                current_headers = ws.row_values(1)
                if current_headers != headers:
                    logger.warning(f"Header mismatch in {name}. Expected: {headers}, Found: {current_headers}")
                    ws.clear()
                    safe_append_row(ws, headers)
                    ws.format("A1:Z1", {
                        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                        "textFormat": {"bold": True}
                    })
                    ws.freeze(rows=1)
                    logger.info(f"Reset headers for worksheet: {name}")
        except Exception as e:
            logger.error(f"Error ensuring worksheet {name}: {e}")
            raise

def fix_menu_items_structure():
    try:
        ws = workbook.worksheet("Menu Items")
        current_headers = ws.row_values(1)
        if current_headers != SHEET_COLUMNS["Menu Items"]:
            all_data = ws.get_all_records()
            ws.clear()
            safe_append_row(ws, SHEET_COLUMNS["Menu Items"])
            for item in all_data:
                new_row = [
                    str(uuid.uuid4()),
                    item.get("name", ""),
                    item.get("price", 0),
                    item.get("description", ""),
                    item.get("category", ""),
                    datetime.now().isoformat()
                ]
                safe_append_row(ws, new_row)
            ws.format("A1:Z1", {
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "textFormat": {"bold": True}
            })
            ws.freeze(rows=1)
            logger.info("Rebuilt Menu Items worksheet structure.")
    except gspread.exceptions.WorksheetNotFound:
        ws = workbook.add_worksheet(title="Menu Items", rows="1000", cols=len(SHEET_COLUMNS["Menu Items"]))
        safe_append_row(ws, SHEET_COLUMNS["Menu Items"])
        ws.format("A1:Z1", {
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
            "textFormat": {"bold": True}
        })
        ws.freeze(rows=1)
        logger.info("Created new Menu Items worksheet.")
    except Exception as e:
        logger.error(f"Error fixing Menu Items structure: {e}")
        raise

ensure_sheets_exist()
fix_menu_items_structure()

class MenuItem(BaseModel):
    name: str
    price: float
    description: str
    category: str

    @validator("price")
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Price must be greater than 0")
        return round(v, 2)

    @validator("name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

class FAQ(BaseModel):
    question: str
    answer: str

    @validator("question", "answer")
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("Fields cannot be empty")
        return v.strip()

class Order(BaseModel):
    phone: str
    name: Optional[str] = "Unknown"
    items: List[str]
    total: float
    special_instructions: Optional[str] = ""
    status: Optional[str] = "New"

    @validator("phone")
    def normalize_phone(cls, v):
        v = v.strip()
        try:
            parsed = phonenumbers.parse(v, None)
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number")
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException:
            raise ValueError("Invalid phone number format")

    @validator("items")
    def at_least_one_item(cls, v):
        if not v:
            raise ValueError("Order must contain at least one item")
        return v

class Reservation(BaseModel):
    phone: str
    name: Optional[str] = "Unknown"
    date: str
    time: str
    party_size: int
    special_requests: Optional[str] = ""
    status: Optional[str] = "New"

    @validator("party_size")
    def party_size_positive(cls, v):
        if v <= 0:
            raise ValueError("Party size must be greater than 0")
        return v

    @validator("phone")
    def normalize_phone(cls, v):
        v = v.strip()
        try:
            parsed = phonenumbers.parse(v, None)
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number")
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException:
            raise ValueError("Invalid phone number format")



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}\n{traceback.format_exc()}")
    return Response(content=json.dumps({"error": str(exc)}), status_code=500, media_type="application/json")

# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    try:
        _ = workbook.worksheet("Menu Items")
        return {"status": "healthy", "sheets_connected": True, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "sheets_connected": False, "timestamp": datetime.now().isoformat()}

@app.get("/api/menu-items")
def get_menu_items():
    try:
        logger.info("Received request: /api/menu-items")
        ws = workbook.worksheet("Menu Items")
        records = ws.get_all_records()
        return records
    except Exception as e:
        logger.error(f"Error fetching menu items: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/menu-items")
def add_menu_item(item: MenuItem):
    try:
        ws = workbook.worksheet("Menu Items")
        row = [
            str(uuid.uuid4()),
            item.name,
            item.price,
            item.description,
            item.category,
            datetime.now().isoformat()
        ]
        safe_append_row(ws, row)
        return {"message": "Added successfully", "id": row[0]}
    except Exception as e:
        logger.error(f"Error adding menu item: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/menu-items/{item_id}")
def update_menu_item(item_id: str, item: MenuItem):
    try:
        ws = workbook.worksheet("Menu Items")
        all_values = ws.get_all_values()
        headers = all_values[0]
        id_col = headers.index("id")

        for idx, row in enumerate(all_values[1:], start=2):
            if row[id_col] == item_id:
                updated_row = [
                    item_id,
                    item.name,
                    item.price,
                    item.description,
                    item.category,
                    datetime.now().isoformat()
                ]
                ws.update(f"A{idx}:F{idx}", [updated_row])
                return {"message": "Menu item updated successfully", "id": item_id}
        raise HTTPException(status_code=404, detail="Menu item not found")
    except Exception as e:
        logger.error(f"Error updating menu item: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/menu-items/{item_id}")
def delete_menu_item(item_id: str):
    try:
        ws = workbook.worksheet("Menu Items")
        all_values = ws.get_all_values()
        headers = all_values[0]
        if "id" not in headers:
            raise HTTPException(status_code=500, detail="Worksheet header missing 'id'")
        id_col = headers.index("id")
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > id_col and row[id_col] == item_id:
                ws.delete_rows(idx)
                return {"message": "Deleted successfully"}
        raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        logger.error(f"Error deleting menu item: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/faqs")
def get_faqs():
    try:
        ws = workbook.worksheet("FAQs")
        all_records = ws.get_all_records()
        
        valid = [r for r in all_records if r.get("id") and r.get("question") and r.get("answer")]
        return valid
    except Exception as e:
        logger.error(f"Error fetching FAQs: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/faqs")
def add_faq(faq: FAQ):
    try:
        ws = workbook.worksheet("FAQs")
        all_values = ws.get_all_values()
        empty_rows = [i + 2 for i, r in enumerate(all_values[1:]) if not any(cell.strip() for cell in r)]
        for ridx in sorted(empty_rows, reverse=True):
            ws.delete_rows(ridx)
        row = [
            str(uuid.uuid4()),
            faq.question,
            faq.answer,
            datetime.now().isoformat()
        ]
        safe_append_row(ws, row)
        return {"message": "Added successfully", "id": row[0]}
    except Exception as e:
        logger.error(f"Error adding FAQ: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/faqs/{faq_id}")
def update_faq(faq_id: str, faq: FAQ):
    try:
        ws = workbook.worksheet("FAQs")
        all_values = ws.get_all_values()
        headers = all_values[0]
        id_col = headers.index("id")

        for idx, row in enumerate(all_values[1:], start=2):
            if row[id_col] == faq_id:
                updated_row = [
                    faq_id,
                    faq.question,
                    faq.answer,
                    datetime.now().isoformat()
                ]
                ws.update(f"A{idx}:D{idx}", [updated_row])
                return {"message": "FAQ updated successfully", "id": faq_id}
        raise HTTPException(status_code=404, detail="FAQ not found")
    except Exception as e:
        logger.error(f"Error updating FAQ: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/faqs/{faq_id}")
def delete_faq(faq_id: str):
    try:
        ws = workbook.worksheet("FAQs")
        all_values = ws.get_all_values()
        for idx, row in enumerate(all_values[1:], start=2):
            if row and row[0] == faq_id:
                ws.delete_rows(idx)
                return {"message": "Deleted successfully"}
        raise HTTPException(status_code=404, detail="FAQ not found")
    except Exception as e:
        logger.error(f"Error deleting FAQ: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders")
def get_orders():
    try:
        ws = workbook.worksheet("Orders")
        values = ws.get_all_values()
        expected_headers = SHEET_COLUMNS["Orders"]

        if not values or len(values) == 0 or values[0] != expected_headers:
            logger.warning(f"Orders sheet header mismatch or missing. Expected: {expected_headers}, Found: {values[0] if values else 'empty'}")
            ws.clear()
            safe_append_row(ws, expected_headers)
            ws.format("A1:Z1", {
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "textFormat": {"bold": True}
            })
            ws.freeze(rows=1)
            return []

        if len(values) == 1:
            return []

        records = ws.get_all_records()
        for record in records:
            try:
                if isinstance(record.get("items"), str) and record["items"]:
                    record["items"] = json.loads(record["items"])
                else:
                    record["items"] = []
                record["name"] = record.get("name", "Unknown")
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in items for order ID {record.get('id', 'unknown')}")
                record["items"] = []
        return records
    except Exception as e:
        logger.error(f"Error fetching orders: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/order-complete")
async def handle_order(request: Request):
    """Handle order requests from VAPI"""
    try:
        payload = await request.json()
        logger.info(f"Received order payload: {payload}")
        
        if not payload.get("message", {}).get("toolCalls", []):
            raise HTTPException(status_code=400, detail="Missing toolCalls in payload")
        order_data = payload['message']['toolCalls'][0]['function']['arguments']
        logger.info(f"Extracted order data: {order_data}")

        order = Order(**order_data)
        if order.total < 0:
            raise ValueError("Order total must be greater than 0")
        
        ws = workbook.worksheet("Orders")
        order_id = str(uuid.uuid4())
        row = [
            order_id,
            datetime.now().isoformat(),
            order.phone,
            order.name,
            json.dumps(order.items),
            order.total,
            order.special_instructions or "",
            order.status
        ]
        safe_append_row(ws, row)
        logger.info(f"Order saved with ID: {order_id}")

        return {
            "success": True,
            "message": "Order saved successfully",
            "id": order_id,
            "order": {
                "phone": order.phone,
                "name": order.name,
                "items": order.items,
                "total": order.total,
                "special_instructions": order.special_instructions,
                "status": order.status
            }
        }
    except KeyError as ke:
        logger.error(f"Missing key in payload: {ke}")
        raise HTTPException(status_code=400, detail=f"Missing required field: {ke}")
    except json.JSONDecodeError as je:
        logger.error(f"JSON decode error: {je}")
        raise HTTPException(status_code=400, detail="Invalid JSON in arguments")
    except ValueError as ve:
        logger.error(f"Validation error in order: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error handling order: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    

@app.post("/api/reservation-complete")
async def handle_reservation(request: Request):
    """Handle reservation requests from VAPI"""
    try:
        payload = await request.json()
        logger.info(f"Received reservation payload: {payload}")
        
        reservation_data = payload['message']['toolCalls'][0]['function']['arguments']
        
        logger.info(f"Extracted reservation data: {reservation_data}")
        reservation = Reservation(**reservation_data)
        
        try:
            datetime.strptime(reservation.date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")
        
        try:
            datetime.strptime(reservation.time, "%H:%M")
        except ValueError:
            raise ValueError("Invalid time format. Use HH:MM (24h)")
        
        if reservation.party_size <= 0 or reservation.party_size > 20:
            raise ValueError("Party size must be between 1 and 20")
        
        ws = workbook.worksheet("Reservations")
        res_id = str(uuid.uuid4())
        
        row = [
            res_id,
            datetime.now().isoformat(),
            reservation.phone,
            reservation.date,
            reservation.time,
            reservation.party_size,
            reservation.special_requests or "None",
            "New"
        ]
        
        ws.append_row(row)
        logger.info(f"Reservation saved with ID: {res_id}")
        
        return {
            "success": True,
            "message": "Reservation saved successfully",
            "id": res_id,
            "reservation": {
                "phone": reservation.phone,
                "date": reservation.date,
                "time": reservation.time,
                "party_size": reservation.party_size,
                "special_requests": reservation.special_requests
            }
        }
        
    except KeyError as ke:
        logger.error(f"Missing key in payload: {ke}")
        raise HTTPException(status_code=400, detail=f"Missing required field: {ke}")
    
    except json.JSONDecodeError as je:
        logger.error(f"JSON decode error: {je}")
        raise HTTPException(status_code=400, detail="Invalid JSON in arguments")
    
    except ValueError as ve:
        logger.error(f"Validation error in reservation: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    
    except Exception as e:
        logger.error(f"Error handling reservation: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.put("/api/orders/{order_id}")
def update_order(order_id: str, order: Order):
    try:
        ws = workbook.worksheet("Orders")
        all_values = ws.get_all_values()
        id_col = all_values[0].index("id")

        for idx, row in enumerate(all_values[1:], start=2):
            if row[id_col] == order_id:
                ws.update(f"A{idx}:H{idx}", [[
                    order_id,
                    datetime.now().isoformat(),
                    order.phone,
                    order.name,
                    json.dumps(order.items),
                    order.total,
                    order.special_instructions,
                    order.status
                ]])
                return {"message": "Order updated successfully", "id": order_id}
        raise HTTPException(status_code=404, detail="Order not found")
    except Exception as e:
        logger.error(f"Error updating order: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/orders/{order_id}")
def delete_order(order_id: str):
    try:
        ws = workbook.worksheet("Orders")
        all_values = ws.get_all_values()
        id_col = all_values[0].index("id")

        for idx, row in enumerate(all_values[1:], start=2):
            if row[id_col] == order_id:
                ws.delete_rows(idx)
                return {"message": "Order deleted successfully"}
        raise HTTPException(status_code=404, detail="Order not found")
    except Exception as e:
        logger.error(f"Error deleting order: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reservations")
def get_reservations():
    try:
        ws = workbook.worksheet("Reservations")
        values = ws.get_all_values()
        expected_headers = SHEET_COLUMNS["Reservations"]

        if not values or len(values) == 0 or values[0] != expected_headers:
            logger.warning(f"Reservations sheet header mismatch or missing. Expected: {expected_headers}, Found: {values[0] if values else 'empty'}")
            ws.clear()
            safe_append_row(ws, expected_headers)
            ws.format("A1:Z1", {
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "textFormat": {"bold": True}
            })
            ws.freeze(rows=1)
            return []
        if len(values) == 1:
            return []

        records = ws.get_all_records()
        for record in records:
            record["name"] = record.get("name", "Unknown")
        return records
    except Exception as e:
        logger.error(f"Error fetching reservations: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))



@app.put("/api/reservations/{res_id}")
def update_reservation(res_id: str, res: Reservation):
    try:
        ws = workbook.worksheet("Reservations")
        all_values = ws.get_all_values()
        id_col = all_values[0].index("id")

        for idx, row in enumerate(all_values[1:], start=2):
            if row[id_col] == res_id:
                ws.update(f"A{idx}:I{idx}", [[
                    res_id,
                    datetime.now().isoformat(),
                    res.phone,
                    res.name,
                    res.date,
                    res.time,
                    res.party_size,
                    res.special_requests,
                    res.status
                ]])
                return {"message": "Reservation updated successfully", "id": res_id}
        raise HTTPException(status_code=404, detail="Reservation not found")
    except Exception as e:
        logger.error(f"Error updating reservation: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/reservations/{res_id}")
def delete_reservation(res_id: str):
    try:
        ws = workbook.worksheet("Reservations")
        all_values = ws.get_all_values()
        headers = all_values[0]
        if "id" not in headers:
            raise HTTPException(status_code=500, detail="Missing 'id' column in Reservations sheet")
        id_col = headers.index("id")

        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > id_col and row[id_col] == res_id:
                ws.delete_rows(idx)
                return {"message": "Reservation deleted successfully"}
        raise HTTPException(status_code=404, detail="Reservation not found")
    except Exception as e:
        logger.error(f"Error deleting reservation: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# ─── Call Logs Endpoints ───────────────────────────────────────────────────────
async def create_call_log(phone: str, call_sid: str):
    """Create initial call log entry when call starts"""
    try:
        call_ws = workbook.worksheet("Call Logs")
        call_id = str(uuid.uuid4())
        row = [
            call_id,
            datetime.now().isoformat(),
            phone,
            "0",
            "in-progress",
            "",
            "",
            ""
        ]
        safe_append_row(call_ws, row)
        logger.info(f"Call log created with ID: {call_id} for phone: {phone}")
        return call_id
    except Exception as e:
        logger.error(f"Error creating call log: {e}")
        return None

# ─── Inbound Call Endpoint ─────────────────────────────────────────────────────
@app.post("/inbound_call")
async def inbound_call(request: Request):
    try:
        form = await request.form()
        caller = form.get("From")
        call_sid = form.get("CallSid")
        logger.info(f"📞 Incoming call from {caller}, CallSid: {call_sid}")

        try:
            menu_ws = workbook.worksheet("Menu Items")
            menu_items = menu_ws.get_all_records()
            faq_ws = workbook.worksheet("FAQs")
            faqs = faq_ws.get_all_records()
            
            menu_text = ""
            categories = {}
            for item in menu_items:
                category = item.get("category", "Other")
                if category not in categories:
                    categories[category] = []
                categories[category].append(f"{item.get('name', '')} - ${item.get('price', 0):.2f}")
            for category, items in categories.items():
                menu_text += f"{category}: {', '.join(items)}. "
            
            faq_text = ""
            for faq in faqs:
                if faq.get("question") and faq.get("answer"):
                    faq_text += f"Q: {faq['question']} A: {faq['answer']} "
        except Exception as e:
            logger.error(f"Error fetching menu/FAQs: {e}")
            menu_text = "Menu temporarily unavailable"
            faq_text = "FAQ information temporarily unavailable"

        payload = {
            "phoneNumberId": VAPI_PHONE_NUMBER_ID,
            "phoneCallProviderBypassEnabled": True,
            "assistantId": VAPI_ASSISTANT_ID,
            "customer": {"number": caller},
            "assistantOverrides": {
                "variableValues": {
                    "menu": menu_text,
                    "faqs": faq_text
                }
            }
        }

        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json"
        }

        logger.info(f"🔄 Making VAPI API call with dynamic menu data")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{VAPI_BASE_URL}/call", json=payload, headers=headers)
            logger.info(f"📡 VAPI Response Status: {resp.status_code}")

            if resp.status_code not in [200, 201]:
                logger.error(f"❌ VAPI API Error: {resp.status_code} - {resp.text}")
                return Response(
                    content="<Response><Say>Unable to connect to assistant</Say></Response>",
                    media_type="application/xml"
                )

            response_data = resp.json()
            if "phoneCallProviderDetails" not in response_data:
                logger.error(f"❌ No phoneCallProviderDetails in response: {response_data}")
                return Response(
                    content="<Response><Say>Assistant configuration error</Say></Response>",
                    media_type="application/xml"
                )

            twiml = response_data["phoneCallProviderDetails"].get("twiml")
            if not twiml or not twiml.strip():
                logger.error(f"❌ Empty TwiML received from VAPI: {response_data}")
                return Response(
                    content="<Response><Say>Assistant response error</Say></Response>",
                    media_type="application/xml"
                )

            logger.info(f"✅ Returning TwiML with dynamic menu data")
            await create_call_log(caller, call_sid)
            return Response(content=twiml, media_type="application/xml")
    except Exception as e:
        logger.error(f"❌ Critical error in inbound_call: {e}\n{traceback.format_exc()}")
        return Response(
            content="<Response><Say>System error</Say></Response>",
            media_type="application/xml"
        )
@app.get("/")
async def root():
    return {"message": "Twilio to VAPI Bridge is running"}

# ─── Uvicorn Entry Point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting server on port {port}")
    logger.info(f"🌐 Visit: http://localhost:{port}")
    logger.info(f"📋 API Docs: http://localhost:{port}/docs")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)