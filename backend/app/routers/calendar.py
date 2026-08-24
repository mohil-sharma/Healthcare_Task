"""Calendar OAuth router."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.core.config import settings

import google_auth_oauthlib.flow

router = APIRouter(prefix="/api/calendar", tags=["calendar"])
logger = logging.getLogger(__name__)

def get_google_flow():
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return None
        
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "project_id": "healthcare-demo",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": ["http://localhost:8000/api/calendar/callback"]
        }
    }
    
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config,
        scopes=["https://www.googleapis.com/auth/calendar.events"]
    )
    flow.redirect_uri = "http://localhost:8000/api/calendar/callback"
    return flow

@router.get("/auth")
async def auth(user_id: int):
    """
    Redirects to Google OAuth screen. 
    In prod, `user_id` must be passed via encrypted JWT in `state` to prevent CSRF.
    """
    flow = get_google_flow()
    if not flow:
        # Mock flow if no API keys are provided
        return RedirectResponse(f"/api/calendar/callback?code=mock_code&state={user_id}")
        
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent', # Force consent to get refresh token
        state=str(user_id)
    )
    return RedirectResponse(auth_url)

@router.get("/callback")
async def callback(state: str, code: str, db: AsyncSession = Depends(get_db)):
    """
    Handles the Google OAuth callback and stores the refresh token securely.
    """
    try:
        user_id = int(state)
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        flow = get_google_flow()
        if not flow:
            # Mock behavior
            user.google_refresh_token = "mock_refresh_token"
            await db.commit()
            return {"detail": "Mock Calendar connected successfully. (Provide Google API keys for real sync)."}
            
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Save refresh token (Google only sends it on initial consent)
        if credentials.refresh_token:
            user.google_refresh_token = credentials.refresh_token
            await db.commit()
            
        return {"detail": "Calendar connected successfully"}
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=400, detail="OAuth failed")
