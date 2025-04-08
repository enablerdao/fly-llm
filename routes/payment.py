from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
import time
import os
import json
import stripe
from datetime import datetime

# Import from litellm proxy
from litellm.proxy.utils import generate_key

router = APIRouter()

# Set Stripe API key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class PaymentRequest(BaseModel):
    email: str
    name: str
    plan: str
    amount: str

@router.post("/create-checkout-session")
async def create_checkout_session(payment_data: PaymentRequest):
    """Create a Stripe checkout session for payment"""
    
    try:
        # Convert amount to integer (in cents/yen)
        amount = int(payment_data.amount)
        
        # Determine bonus credit based on plan
        bonus_percentage = 0
        if payment_data.plan == "プロ":
            bonus_percentage = 5
        elif payment_data.plan == "エンタープライズ":
            bonus_percentage = 10
            
        # Calculate total credit amount including bonus
        total_credit = amount * (1 + bonus_percentage / 100)
        
        # Convert to USD (approximate conversion for budget setting)
        usd_amount = amount / 140  # Approximate JPY to USD conversion
        usd_total = total_credit / 140
        
        # Create a checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "jpy",
                        "product_data": {
                            "name": f"Fly-LLM {payment_data.plan} プラン",
                            "description": f"{amount}円のクレジット" + (f" (+{bonus_percentage}%ボーナス)" if bonus_percentage > 0 else ""),
                        },
                        "unit_amount": amount,
                    },
                    "quantity": 1,
                },
            ],
            mode="payment",
            success_url=f"{os.getenv('SITE_URL', 'https://fly-llm-api.fly.dev')}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('SITE_URL', 'https://fly-llm-api.fly.dev')}/payment-cancel",
            customer_email=payment_data.email,
            metadata={
                "name": payment_data.name,
                "plan": payment_data.plan,
                "amount": str(amount),
                "bonus_percentage": str(bonus_percentage),
                "total_credit": str(total_credit),
            },
        )
        
        # Generate a new API key
        key_name = f"{payment_data.name}-{payment_data.plan}-{int(time.time())}"
        api_key = generate_key(key_name, max_budget=usd_total)
        
        # Store the API key with the checkout session for retrieval after payment
        # In a production environment, you would use a database for this
        session_data = {
            "checkout_session_id": checkout_session.id,
            "api_key": api_key["key"],
            "created_at": datetime.now().isoformat(),
            "email": payment_data.email,
            "name": payment_data.name,
            "plan": payment_data.plan,
            "amount": amount,
            "total_credit": total_credit,
        }
        
        # Store session data in a file
        session_file = f"/app/data/payment_sessions/{checkout_session.id}.json"
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        with open(session_file, "w") as f:
            json.dump(session_data, f, indent=2)
        
        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
            "api_key": api_key["key"],
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating checkout session: {str(e)}")

@router.get("/payment-success")
async def payment_success(session_id: str):
    """Handle successful payment"""
    
    try:
        # Verify the payment was successful
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status != "paid":
            raise HTTPException(status_code=400, detail="Payment not completed")
        
        # Retrieve the API key from the stored session data
        session_file = f"/app/data/payment_sessions/{session_id}.json"
        if not os.path.exists(session_file):
            raise HTTPException(status_code=404, detail="Session data not found")
            
        with open(session_file, "r") as f:
            session_data = json.load(f)
        
        return {
            "success": True,
            "message": "Payment successful! Your API key has been generated.",
            "api_key": session_data["api_key"],
            "plan": session_data["plan"],
            "amount": session_data["amount"],
            "total_credit": session_data["total_credit"],
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing payment: {str(e)}")

@router.get("/payment-cancel")
async def payment_cancel():
    """Handle cancelled payment"""
    
    return {
        "success": False,
        "message": "Payment was cancelled. No charges were made."
    }