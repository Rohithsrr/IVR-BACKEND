import os
import random
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
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

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
VERIFIED_TO_NUMBER = os.getenv("VERIFIED_TO_NUMBER")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

generated_codes = {}
verified_users = {}


class StartIvrRequest(BaseModel):
    user: str | None = None
    email: str | None = None


@app.get("/")
async def root():
    return {"message": "IVR backend is running"}


@app.post("/start-ivr")
async def start_ivr(payload: StartIvrRequest):
    user = payload.email or payload.user or "unknown"

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


@app.api_route("/ivr/twiml", methods=["GET", "POST"])
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
        action=f"{PUBLIC_BASE_URL}/ivr/verify?user={quote(user)}",
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
