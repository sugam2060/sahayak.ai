import os
import json
import httpx
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Sahayak WhatsApp Webhook & Signup Tester")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================== CONFIG ==================
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "sahayak_whatsapp_token_123")
APP_ID = "1156089379988807"
APP_SECRET = os.getenv("FACEBOOK_APP_SECRET") # Must be set in .env for token exchange

if not APP_SECRET:
    print("⚠️  Warning: FACEBOOK_APP_SECRET not set in .env. Token exchange will fail.")
# ============================================

@app.get("/signup", response_class=HTMLResponse)
async def serve_signup_page():
    """Serves the WhatsApp Embedded Signup HTML page."""
    html_path = os.path.join(os.path.dirname(__file__), "whatsapp_signup.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Signup Page Not Found</h1>", status_code=404)


@app.post("/whatsapp/signup-callback")
async def whatsapp_signup_callback(request: Request):
    """
    Handles the code returned by the Embedded Signup flow and exchanges it for a token.
    """
    data = await request.json()
    code = data.get("code")

    if not code:
        raise HTTPException(status_code=400, detail="No code provided")

    if not APP_SECRET:
        return JSONResponse({
            "status": "error", 
            "error": "APP_SECRET not configured on server",
            "received_code": code
        }, status_code=500)

    # Step: Exchange code for User Access Token
    # Endpoint: GET https://graph.facebook.com/v21.0/oauth/access_token
    token_url = "https://graph.facebook.com/v21.0/oauth/access_token"
    params = {
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "code": code
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(token_url, params=params)
            token_data = response.json()
            
            if "access_token" in token_data:
                user_access_token = token_data["access_token"]
                print(f"✅ Received User Access Token: {user_access_token[:10]}...")
                
                # In a real app, you would now use this token to:
                # 1. Get WABA ID (WhatsApp Business Account ID)
                # 2. Get Phone Number ID
                # 3. Subscribe to webhooks
                
                return {
                    "status": "success",
                    "message": "Token retrieved successfully",
                    "token_preview": f"{user_access_token[:10]}...",
                    "full_response": token_data
                }
            else:
                print(f"❌ Token Exchange Failed: {token_data}")
                return JSONResponse({
                    "status": "error",
                    "error": "Failed to exchange code",
                    "details": token_data
                }, status_code=400)
                
        except Exception as e:
            print(f"❌ Request Error: {str(e)}")
            return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.get("/webhook")
async def verify_webhook(
    mode: Optional[str] = Query(None, alias="hub.mode"),
    token: Optional[str] = Query(None, alias="hub.verify_token"),
    challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    """WhatsApp Webhook Verification (GET)"""
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("✅ WhatsApp Webhook verified successfully!")
            return PlainTextResponse(content=challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def handle_webhook(request: Request):
    """WhatsApp Webhook Notification (POST)"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if body.get("object") == "whatsapp_business_account":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for message in value["messages"]:
                        sender_id = message.get("from")
                        sender_name = value.get("contacts", [{}])[0].get("profile", {}).get("name", "Unknown")
                        if message.get("type") == "text":
                            text = message.get("text", {}).get("body")
                            print(f"📩 [WHATSAPP MESSAGE] From: {sender_name} ({sender_id}) | Text: {text}")
                elif "statuses" in value:
                    for status in value["statuses"]:
                        print(f"🔄 [WHATSAPP STATUS] To: {status.get('recipient_id')} | Status: {status.get('status')}")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    return JSONResponse(content={"status": "not_whatsapp_account"}, status_code=200)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    print(f"🚀 WhatsApp Signup & Webhook Tester running on http://localhost:{port}")
    print(f"👉 Signup UI: http://localhost:{port}/signup")
    uvicorn.run(app, host="localhost", port=port)