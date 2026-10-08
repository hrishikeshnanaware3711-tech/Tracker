# Daily Journal

A very small full-stack journal for a 45-minute workshop. Users verify their phone with MiniMoth OTP, then create and edit personal journal entries.

## Stack
- React + Vite
- FastAPI
- SQLite
- MiniMoth OTP API

## Project limits
- Frontend pages: 2 (Auth, Journal)
- Backend API endpoints: 5 (`/api/auth/send-otp`, `/api/auth/verify-otp`, `/api/entries` GET, `/api/entries` POST, `/api/entries/{id}` PUT)
- Database entities: 2 (`users`, `journal_entries`)

## Setup

### 1. MiniMoth key
Create a MiniMoth project and copy its API key. For a no-credit workshop flow, MiniMoth also provides test keys/sandbox support. The API key must stay in the backend `.env`. MiniMoth's current REST API uses the `X-Api-Key` header. 

Copy:

```text
backend/.env.example -> backend/.env
frontend/.env.example -> frontend/.env
```

Set `MINIMOTH_API_KEY` in `backend/.env`.

### 2. Backend

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`.

### 3. Frontend
Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually `http://localhost:5173`.

The Vite dev proxy forwards `/api` to FastAPI, so no CORS configuration is needed for local development.

## OTP flow
1. Enter a mobile number.
2. FastAPI calls MiniMoth `POST /v1/otp/send`.
3. Enter the 6-digit code.
4. FastAPI calls MiniMoth `POST /v1/otp/verify`.
5. The returned MiniMoth access token is stored in the browser and sent as a Bearer token for journal requests.

MiniMoth access tokens are short-lived, so this workshop version intentionally keeps session handling minimal; re-verify the phone when the token expires.

## Notes
The MiniMoth API and OTP behavior used here follow the current public documentation. The service sends WhatsApp first and can fall back to SMS. `otp/verify` returns an access token and identity ID on success.
