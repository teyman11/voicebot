# Restaurant Voice Bot System

A web-based restaurant management system with voice bot integration for handling orders and reservations.

## Features

- Menu Items Management
- FAQs Management
- Order Tracking
- Reservation Management
- Voice Bot Integration with VAPI
- Google Sheets Integration for Data Storage

## Project Structure

```
.
├── backend/
│   ├── app.py              # FastAPI backend server
│   ├── requirements.txt    # Python dependencies
│   └── credentials.json    # Google Sheets credentials (you need to add this)
├── frontend/
│   ├── src/
│   │   └── App.jsx        # React frontend application
│   └── package.json       # Node.js dependencies
└── .env                   # Environment variables
```

## Prerequisites

1. Python 3.8 or higher
2. Node.js 14 or higher
3. Google Cloud account with Sheets API enabled
4. Twilio account
5. VAPI assistant setup

## Setup Instructions

### Backend Setup

1. Create and activate virtual environment:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up Google Sheets:
   - Create a Google Cloud project
   - Enable Google Sheets API
   - Create a service account
   - Download credentials as `credentials.json`
   - Place `credentials.json` in the backend folder
   - Create a Google Sheet and share it with the service account email

4. Create `.env` file in backend directory:
   ```
   GOOGLE_SHEET_ID=your_sheet_id_here
   VAPI_WEBHOOK_URL=your_vapi_assistant_url
   ```

### Frontend Setup

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. The frontend will automatically connect to the backend at `http://localhost:8000`

## Running the Application

1. Start the backend server:
   ```bash
   cd backend
   python app.py
   ```

2. Start the frontend development server:
   ```bash
   cd frontend
   npm start
   ```

3. Access the application at `http://localhost:3000`

## Integration Points

### Twilio Setup

1. Get a Twilio phone number
2. Set the voice webhook URL to your backend's `/api/voice` endpoint
3. The system will redirect calls to your VAPI assistant

### VAPI Integration

Your VAPI assistant should be configured to:

1. Handle the initial call redirect from `/api/voice`
2. Send completed orders to `/api/order-complete` with:
   ```json
   {
     "phone": "customer_phone",
     "items": ["item1", "item2"],
     "total": 50.00,
     "special_instructions": "extra spicy"
   }
   ```
3. Send completed reservations to `/api/reservation-complete` with:
   ```json
   {
     "phone": "customer_phone",
     "date": "2024-03-20",
     "time": "19:00",
     "party_size": 4,
     "special_requests": "window seat"
   }
   ```

### Google Sheets Structure

The system automatically creates these sheets:
- Menu Items (name, price, description)
- FAQs (question, answer)
- Orders (time, phone, items, total)
- Reservations (time, phone, date, party_size)

## Development

The application uses:
- FastAPI for the backend
- React with Material-UI for the frontend
- Google Sheets for data storage
- Twilio for voice call handling
- VAPI for voice assistant functionality 