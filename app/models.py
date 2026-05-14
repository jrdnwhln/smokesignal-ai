from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str
    phone_number: str
    sms_enabled: bool = False
    voice_mode: str = Field(default="clean_retail", pattern="^(professional|clean_retail|market_homie)$")


class TestSmsRequest(BaseModel):
    phone_number: str
    message: str


class SmsWebhookRequest(BaseModel):
    From: str | None = None
    Body: str | None = None
