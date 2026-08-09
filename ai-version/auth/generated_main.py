import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import create_client


app = FastAPI(title="AI Supabase Auth API")
security = HTTPBearer()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


class Login(BaseModel):
    email: str
    password: str


def user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        return supabase.auth.get_user(credentials.credentials).user
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


@app.post("/auth/signup", status_code=201)
def signup(payload: Login):
    return supabase.auth.sign_up(payload.model_dump()).user


@app.post("/auth/login")
def login(payload: Login):
    session = supabase.auth.sign_in_with_password(payload.model_dump()).session
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }


@app.get("/public/info")
def public_info():
    return {"message": "Welcome stranger! This info is public."}


@app.get("/protected/profile")
def profile(current_user=Depends(user)):
    return {"id": current_user.id, "email": current_user.email}


@app.get("/protected/dashboard")
def dashboard(current_user=Depends(user)):
    return {"user_id": current_user.id}
