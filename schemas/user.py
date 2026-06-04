from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class SendOtpRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class RegisterCompleteRequest(BaseModel):
    firstName: str
    lastName: str
    email: str
    phone: str
    address: str
    password: str


class ResetPasswordRequest(BaseModel):
    email: str
    newPassword: str


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    birthday: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None


class AdminCreateUserRequest(BaseModel):
    name: str
    email: str
    password: str
    role: int


class AdminUpdateUserRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[int] = None
    status: Optional[str] = None
