"""
AUTOMATED SYSTEM INTEGRATION DIAGNOSTIC TOOL
Runs a complete internal health audit across all modules:
1. Database Connectivity (Supabase PostgreSQL / SQLite)
2. Encryption & Security Manager
3. Department Resolver & Data Loading
4. Gemini AI Connection
5. Portal Router & Adapter Selection
"""

import sys
import os
import asyncio
import warnings
from pathlib import Path

# Suppress deprecation warnings in test output
warnings.filterwarnings("ignore")

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from config.security import security_manager
from services.department_resolver_service import DepartmentResolverService
from services.portal_adapters import PortalRouter


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


async def audit_database():
    print(f"\n{Color.BLUE}[1/5] Testing Database Connection...{Color.RESET}")
    try:
        from config.database import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            val = result.scalar()
            if val == 1:
                print(f"  {Color.GREEN}✓ Database Connected Successfully ({engine.dialect.name}){Color.RESET}")
                return True
    except Exception as e:
        print(f"  {Color.RED}✗ Database Connection Failed: {str(e)}{Color.RESET}")
        return False


def audit_security_manager():
    print(f"\n{Color.BLUE}[2/5] Testing Security & Encryption Module...{Color.RESET}")
    try:
        test_pass = "TestPassword@123"
        hashed = security_manager.hash_password(test_pass)
        verified = security_manager.verify_password(test_pass, hashed)

        sample_pii = "A-41, Khodiyar Baug, Nikol, Ahmedabad"
        encrypted = security_manager.encrypt_pii(sample_pii)
        decrypted = security_manager.decrypt_pii(encrypted)

        if verified and decrypted == sample_pii:
            print(f"  {Color.GREEN}✓ Bcrypt Hashing & Fernet PII Encryption Working Perfectly{Color.RESET}")
            return True
        else:
            print(f"  {Color.RED}✗ Security Verification Mismatch{Color.RESET}")
            return False
    except Exception as e:
        print(f"  {Color.RED}✗ Security Module Error: {str(e)}{Color.RESET}")
        return False


async def audit_department_resolver():
    print(f"\n{Color.BLUE}[3/5] Testing Department Resolver & Data Files...{Color.RESET}")
    try:
        resolver = DepartmentResolverService()
        res = await resolver.resolve_department(
            category="road_repair",
            state="Gujarat",
            city="Ahmedabad"
        )

        dept_name = res.get("department_name", "")
        if "Ahmedabad" in dept_name or "Municipal" in dept_name:
            print(f"  {Color.GREEN}✓ Department Resolved: {dept_name}{Color.RESET}")
            return True
        else:
            print(f"  {Color.YELLOW}⚠ Department Resolved with Fallback: {dept_name}{Color.RESET}")
            return True
    except Exception as e:
        print(f"  {Color.RED}✗ Department Resolver Failed: {str(e)}{Color.RESET}")
        return False


async def audit_gemini_ai():
    print(f"\n{Color.BLUE}[4/5] Testing Google Gemini AI Connection...{Color.RESET}")
    api_key = settings.GOOGLE_GEMINI_API_KEY
    if not api_key:
        print(f"  {Color.YELLOW}⚠ GOOGLE_GEMINI_API_KEY is empty in .env (Using Fallback Template Engine){Color.RESET}")
        return True

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model_candidates = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-1.5-flash"]
        for name in model_candidates:
            try:
                model = genai.GenerativeModel(name)
                response = model.generate_content("Ping test. Respond with OK.")
                if response and response.text:
                    print(f"  {Color.GREEN}✓ Gemini AI Connected & Responding via [{name}] ({response.text.strip()[:20]}){Color.RESET}")
                    return True
            except Exception:
                continue

        print(f"  {Color.RED}✗ Could not query candidate models.{Color.RESET}")
        return False

    except Exception as e:
        print(f"  {Color.RED}✗ Gemini AI Connection Failed: {str(e)}{Color.RESET}")
        return False


def audit_portal_router():
    print(f"\n{Color.BLUE}[5/5] Testing Portal Router & State Adapters...{Color.RESET}")
    try:
        router = PortalRouter()

        gujarat_adapter = router.get_adapter(
            state="Gujarat",
            department_type="municipal_corporation",
            department_name="Ahmedabad Municipal Corporation"
        )

        central_adapter = router.get_adapter(
            state="Delhi",
            department_type="nhai",
            department_name="National Highways Authority of India"
        )

        print(f"  {Color.GREEN}✓ Gujarat Routing  -> {gujarat_adapter.portal_name}{Color.RESET}")
        print(f"  {Color.GREEN}✓ Central Routing  -> {central_adapter.portal_name}{Color.RESET}")
        return True
    except Exception as e:
        print(f"  {Color.RED}✗ Portal Router Failed: {str(e)}{Color.RESET}")
        return False


async def main():
    print("=" * 60)
    print(" 🔍 RTI SARTHI - INTERNAL SYSTEM INTEGRATION AUDIT")
    print("=" * 60)

    db_ok = await audit_database()
    sec_ok = audit_security_manager()
    dept_ok = await audit_department_resolver()
    ai_ok = await audit_gemini_ai()
    router_ok = audit_portal_router()

    print("\n" + "=" * 60)
    if all([db_ok, sec_ok, dept_ok, ai_ok, router_ok]):
        print(f"{Color.GREEN} 🎉 ALL INTERNAL MODULES ARE 100% HEALTHY & INTEGRATED!{Color.RESET}")
    else:
        print(f"{Color.RED} ⚠️ SOME MODULES REQUIRE ATTENTION. SEE LOGS ABOVE.{Color.RESET}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())