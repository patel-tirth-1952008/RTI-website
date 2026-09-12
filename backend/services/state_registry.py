"""
RTI Sarthi - Indian State & Central RTI Portal Registry
Defines portal URLs, jurisdiction rules, and authentication requirements.
"""

from typing import Dict, Any, Optional

PORTAL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "GUJARAT": {
        "name": "Gujarat State RTI Portal",
        "url": "https://onlinerti.gujarat.gov.in/rti_portal/",
        "auth_required": False,  # Supports direct guest filing
        "type": "STATE",
        "supported_departments": ["Ahmedabad Municipal Corporation", "Urban Development", "Revenue", "GPCB", "RTO"]
    },
    "MAHARASHTRA": {
        "name": "Maharashtra Online RTI Portal",
        "url": "https://rtionline.maharashtra.gov.in/",
        "auth_required": True,   # Requires user account login/registration
        "type": "STATE",
        "supported_departments": ["BMC", "Pune Municipal Corporation", "Revenue", "PWD"]
    },
    "MADHYA PRADESH": {
        "name": "MP RTI Online Portal",
        "url": "https://rtionline.mp.gov.in/",
        "auth_required": True,
        "type": "STATE",
        "supported_departments": ["Indore Municipal Corporation", "Bhopal Smart City", "Urban Administration"]
    },
    "DELHI": {
        "name": "e-RTI Portal Delhi",
        "url": "https://rtionline.delhi.gov.in/",
        "auth_required": True,
        "type": "STATE",
        "supported_departments": ["MCD", "Delhi Jal Board", "PWT", "Revenue"]
    },
    "CENTRAL": {
        "name": "Central Government RTI Portal",
        "url": "https://rtionline.gov.in/request/request.php",
        "auth_required": False,  # Supports guest request filing
        "type": "CENTRAL",
        "supported_departments": ["NHAI", "Indian Railways", "Passport Office", "Income Tax", "CPWD"]
    }
}


def resolve_portal_config(state: str, department: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolves the state portal configuration based on user location and department.
    Guarantees strict jurisdiction separation.
    """
    state_clean = (state or "").strip().upper()
    
    # Check if explicitly matched state exists
    if state_clean in PORTAL_REGISTRY:
        return PORTAL_REGISTRY[state_clean]
    
    # Check alias keywords
    if "GUJ" in state_clean or "AHMEDABAD" in (department or "").upper():
        return PORTAL_REGISTRY["GUJARAT"]
    elif "MAHA" in state_clean or "MUMBAI" in (department or "").upper() or "PUNE" in (department or "").upper():
        return PORTAL_REGISTRY["MAHARASHTRA"]
    elif "DELHI" in state_clean or "MCD" in (department or "").upper():
        return PORTAL_REGISTRY["DELHI"]
    elif "MP" in state_clean or "INDORE" in (department or "").upper() or "BHOPAL" in (department or "").upper():
        return PORTAL_REGISTRY["MADHYA PRADESH"]
        
    # Default fallback to Central Portal if no state match found
    return PORTAL_REGISTRY["CENTRAL"]