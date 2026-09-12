from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import asyncio

from backend.database import get_db
from backend.services.universal_portal_agent import UniversalPortalAgent
from backend.models.rti_request import RTIRequest

router = APIRouter(prefix="/api/v1/rti", tags=["RTI Automation"])


@router.post("/auto-file-state-portal/{rti_id}")
async def auto_file_state_portal(
    rti_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers the autonomous agent to log in/register on the working state portal,
    fills the RTI application, and captures the official ₹10 government payment link.
    """
    # Fetch RTI Record from Database
    rti_record = await db.get(RTIRequest, rti_id)
    if not rti_record:
        raise HTTPException(status_code=404, detail="RTI Application not found")

    user_info = {
        "full_name": rti_record.applicant_name,
        "email": rti_record.applicant_email,
        "phone": rti_record.applicant_phone,
        "address": rti_record.applicant_address,
        "pincode": rti_record.pincode,
        "portal_password": "RTI_Sarthi_User_2025!"
    }

    agent = UniversalPortalAgent()

    # Execute Playwright synchronously in background thread to prevent loop conflicts
    result = await asyncio.to_thread(
        agent.execute_filing_and_get_payment_link,
        user_info=user_info,
        rti_text=rti_record.rti_text_content,
        state=rti_record.state,
        department=rti_record.department_name,
        file_path=rti_record.evidence_image_path
    )

    if result.get("success"):
        rti_record.status = "PAYMENT_PENDING"
        rti_record.payment_url = result.get("payment_url")
        if result.get("registration_no"):
            rti_record.govt_registration_number = result.get("registration_no")
            rti_record.status = "OFFICIALLY_SUBMITTED"
        
        await db.commit()
        await db.refresh(rti_record)

    return {
        "status": "success",
        "data": {
            "rti_id": rti_id,
            "portal_name": result.get("portal_name"),
            "payment_url": result.get("payment_url"),
            "registration_no": result.get("registration_no"),
            "status": rti_record.status,
            "message": result.get("message")
        }
    }