from fastapi import APIRouter, Depends
from services.portal_adapters.gujarat_adapter import run_gujarat_filing_sync

router = APIRouter()

@router.post("/api/rti/submit")
async def submit_rti_to_portal(draft_id: str, user_id: str):
    # 1. Fetch user data from your Database
    user_data = get_user_from_db(user_id)  
    # Returns: {"name": "Tirth", "phone": "9898810531", "address": "...", ...}
    
    # 2. Fetch AI Draft from your Database
    draft_data = get_draft_from_db(draft_id) 
    # Returns: {"rti_text": "Under section 6(1)...", "department": "Ahmedabad Municipal Corporation"}

    # 3. RUN THE AGENT WITH THE LIVE DRAFT DATA
    result = run_gujarat_filing_sync(
        applicant_data=user_data,
        rti_text=draft_data["rti_text"],             # Passed directly from AI Draft!
        department_name=draft_data["department"]     # Passed directly from AI Draft!
    )

    # 4. Return the payment URL to your frontend dashboard
    if result["success"]:
        update_db_status(draft_id, status="PAYMENT_PENDING", payment_url=result["payment_url"])
        return {"message": "Success! Pay the fee.", "payment_url": result["payment_url"]}
    else:
        return {"error": result["error"]}