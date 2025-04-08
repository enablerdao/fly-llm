from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
import time
import uuid
import os
import json
from datetime import datetime
import hashlib
import ipaddress

# Import from litellm proxy
from litellm.proxy.utils import generate_key

router = APIRouter()

# Store used coupons with IP and cookie info
USED_COUPONS_FILE = "/app/data/used_coupons.json"

# Ensure the file exists
if not os.path.exists(USED_COUPONS_FILE):
    with open(USED_COUPONS_FILE, "w") as f:
        json.dump({"used_coupons": []}, f)

class CouponRequest(BaseModel):
    coupon_code: str
    email: Optional[str] = None

def get_client_info(request: Request):
    """Get client IP and user agent for tracking"""
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "")
    
    # Create a unique identifier based on IP and user agent
    client_hash = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()
    
    return {
        "ip": client_ip,
        "user_agent": user_agent,
        "client_hash": client_hash
    }

def has_used_coupon(client_info):
    """Check if this client has already used a coupon"""
    try:
        with open(USED_COUPONS_FILE, "r") as f:
            data = json.load(f)
            
        for entry in data["used_coupons"]:
            if entry["client_hash"] == client_info["client_hash"]:
                return True
                
        # Also check IP address (even if hash is different)
        client_ip = client_info["ip"]
        for entry in data["used_coupons"]:
            if entry["ip"] == client_ip:
                return True
                
        return False
    except Exception as e:
        print(f"Error checking coupon usage: {str(e)}")
        return False

def record_coupon_usage(client_info, coupon_code):
    """Record that this client has used a coupon"""
    try:
        with open(USED_COUPONS_FILE, "r") as f:
            data = json.load(f)
            
        data["used_coupons"].append({
            "client_hash": client_info["client_hash"],
            "ip": client_info["ip"],
            "coupon_code": coupon_code,
            "used_at": datetime.now().isoformat()
        })
        
        with open(USED_COUPONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
            
    except Exception as e:
        print(f"Error recording coupon usage: {str(e)}")

@router.post("/apply-coupon")
async def apply_coupon(request: Request, coupon_data: CouponRequest):
    """Apply a coupon code to get free credits"""
    
    # Get client info for tracking
    client_info = get_client_info(request)
    
    # Check if this client has already used a coupon
    if has_used_coupon(client_info):
        raise HTTPException(status_code=400, detail="You have already used a coupon code.")
    
    # Validate the coupon code (case insensitive)
    if coupon_data.coupon_code.upper() != "TEAI.IO":
        raise HTTPException(status_code=400, detail="Invalid coupon code.")
    
    # Generate a new API key
    key_name = f"coupon-user-{int(time.time())}"
    if coupon_data.email:
        key_name = f"coupon-{coupon_data.email}"
        
    # Create API key with 1000 JPY budget (approximately $7-8 USD)
    api_key = generate_key(key_name, max_budget=7.0)
    
    # Record that this client has used a coupon
    record_coupon_usage(client_info, coupon_data.coupon_code)
    
    return {
        "success": True,
        "message": "Coupon applied successfully! 1,000円 worth of credits have been added to your account.",
        "api_key": api_key["key"],
        "expires_at": api_key["expires_at"],
        "max_budget": api_key["max_budget"]
    }