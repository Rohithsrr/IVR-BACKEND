import os
import random
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
VERIFIED_TO_NUMBER = os.getenv("VERIFIED_TO_NUMBER")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

generated_codes = {}
verified_users = {}


@app.post("/start-ivr")
async def start_ivr(request: Request):
    data = await request.json()
    user = data.get("email") or data.get("user") or "unknown"

    code = f"{random.randint(0, 999999):06d}"
    generated_codes[user] = code
    verified_users[user] = False

    twiml_url = f"{PUBLIC_BASE_URL}/ivr/twiml?user={quote(user)}"

    call = twilio_client.calls.create(
        to=VERIFIED_TO_NUMBER,
        from_=TWILIO_FROM_NUMBER,
        url=twiml_url
    )

    return {
        "message": "IVR call started.",
        "user": user,
        "callSid": call.sid
    }


@app.get("/ivr/twiml")
async def ivr_twiml(user: str):
    code = generated_codes.get(user)

    vr = VoiceResponse()

    if not code:
        vr.say("No verification code was found.")
        vr.hangup()
        return Response(content=str(vr), media_type="application/xml")

    gather = Gather(
        input="dtmf",
        num_digits=6,
        action=f"/ivr/verify?user={quote(user)}",
        method="POST"
    )
    gather.say(f"Your verification code is {code}. Please enter the 6 digits now.")
    vr.append(gather)

    vr.say("No input received. Goodbye.")
    vr.hangup()

    return Response(content=str(vr), media_type="application/xml")


@app.post("/ivr/verify")
async def ivr_verify(request: Request, user: str):
    form = await request.form()
    digits = form.get("Digits", "")

    vr = VoiceResponse()

    if digits == generated_codes.get(user):
        verified_users[user] = True
        vr.say("Verification successful.")
    else:
        verified_users[user] = False
        vr.say("Incorrect code. Verification failed.")

    vr.hangup()
    return Response(content=str(vr), media_type="application/xml")


@app.get("/status")
async def status(user: str):
    return {
        "user": user,
        "verified": verified_users.get(user, False)
    }