from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str
    phone_number: str
    sms_enabled: bool = False
    voice_mode: str = Field(default="normal_clanka")


class SubscribeRequest(BaseModel):
    name: str = "SmokeSignal User"
    phone_number: str
    voice_mode: str = Field(default="twin")


class TestSmsRequest(BaseModel):
    phone_number: str
    message: str


class SmsWebhookRequest(BaseModel):
    From: str | None = None
    Body: str | None = None
