"""
RTI Sarthi - Universal State Portal Automation Agent
Executes multi-step user login/registration, form filling, OCR solver, 
and payment gateway link capture.
"""

import asyncio
import logging
import re
from typing import Dict, Any, Tuple, Optional
from playwright.sync_api import sync_playwright, Page, BrowserContext
from backend.services.captcha_service import CaptchaSolver
from backend.services.state_registry import resolve_portal_config
from backend.core.config import settings

logger = logging.getLogger(__name__)


class UniversalPortalAgent:
    def __init__(self, debug: bool = settings.DEBUG):
        self.debug = debug
        self.captcha_solver = CaptchaSolver()

    def execute_filing_and_get_payment_link(
        self,
        user_info: Dict[str, Any],
        rti_text: str,
        state: str,
        department: str,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main execution loop. Returns payment URL, application draft ID, or direct registration number.
        """
        portal_config = resolve_portal_config(state=state, department=department)
        logger.info(f"Targeting Portal: {portal_config['name']} at {portal_config['url']}")

        # Visual mode in Debug, Headless in Production
        headless_mode = not self.debug

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless_mode,
                args=settings.CHROMIUM_LOW_MEM_FLAGS,
                slow_mo=80 if self.debug else 0
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            captured_payment_url = {"url": None, "post_data": None}

            # Intercept network requests to capture Payment Gateway Redirects (SBI ePay / Treasury)
            def intercept_request(request):
                url = request.url
                if any(pg in url.lower() for pg in ["payment", "gateway", "sbi", "treasury", "egras", "billdesk", "pay"]):
                    logger.info(f"Intercepted Official Govt Payment Gateway URL: {url}")
                    captured_payment_url["url"] = url
                    if request.post_data:
                        captured_payment_url["post_data"] = request.post_data

            page.on("request", intercept_request)

            try:
                # Step 1: Navigate to Government Portal
                page.goto(portal_config["url"], wait_until="networkidle", timeout=45000)

                # Step 2: Handle Authentication (Login / Auto-Register if required)
                if portal_config.get("auth_required", False):
                    self._ensure_user_authenticated(page, user_info)

                # Step 3: Navigate to RTI Request Form
                self._navigate_to_request_form(page, portal_config)

                # Step 4: Auto-Fill Form & Inject AI RTI Application
                self._fill_rti_application_form(page, user_info, rti_text, department, file_path)

                # Step 5: Solve CAPTCHA
                self._solve_portal_captcha(page)

                # Step 6: Submit Form & Trigger Payment
                logger.info("Submitting RTI form to reach Government Payment Gateway...")
                
                # Look for Submit / Pay Fee buttons
                submit_selectors = [
                    "input[type='submit']", "button[type='submit']",
                    "button:has-text('Make Payment')", "button:has-text('Proceed to Payment')",
                    "button:has-text('Submit')", "input[value='Submit']", "a:has-text('Pay Fee')"
                ]

                clicked = False
                for sel in submit_selectors:
                    if page.is_visible(sel):
                        page.click(sel)
                        clicked = True
                        break

                page.wait_for_timeout(4000)

                # Check if direct payment link was intercepted
                final_payment_url = captured_payment_url["url"] or page.url

                # Check if registration number was generated directly
                reg_no_match = re.search(r"RTI/[A-Z0-9]+/\d{4}/\d+", page.content())
                reg_no = reg_no_match.group(0) if reg_no_match else None

                logger.info(f"Filing process complete. Payment URL: {final_payment_url}, Reg No: {reg_no}")

                return {
                    "success": True,
                    "portal_name": portal_config["name"],
                    "payment_url": final_payment_url,
                    "registration_no": reg_no,
                    "status": "PAYMENT_PENDING" if final_payment_url else "SUBMITTED",
                    "message": "RTI application prepared successfully. Click to pay official ₹10 fee."
                }

            except Exception as e:
                logger.error(f"Error during automated RTI filing: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "portal_name": portal_config["name"],
                    "payment_url": portal_config["url"],
                    "error": str(e),
                    "message": f"Automation paused on {portal_config['name']}. You can proceed manually via direct link."
                }
            finally:
                browser.close()

    def _ensure_user_authenticated(self, page: Page, user_info: Dict[str, Any]):
        """
        Automates Portal Login. If login fails or user has no account,
        auto-triggers registration on the portal using user profile info.
        """
        logger.info("Portal requires account. Checking Login / Registration status...")
        
        # Check if login link exists
        if page.is_visible("text=Login") or page.is_visible("a:has-text('Sign In')"):
            if page.is_visible("a:has-text('Login')"):
                page.click("a:has-text('Login')")
            elif page.is_visible("a:has-text('Sign In')"):
                page.click("a:has-text('Sign In')")

            page.wait_for_timeout(1500)

            # Try to log in with user credentials
            email = user_info.get("email", "")
            mobile = user_info.get("phone", "")
            
            # Form field selectors common in state portals
            username_field = page.query_selector("input[type='text'], input[name*='user'], input[name*='email'], input[name*='mobile']")
            password_field = page.query_selector("input[type='password']")

            if username_field and password_field:
                username_field.fill(email or mobile)
                password_field.fill(user_info.get("portal_password", "RTI_Sarthi_User_2025!"))
                
                # Solve Login CAPTCHA if present
                self._solve_portal_captcha(page)

                page.click("button[type='submit'], input[type='submit'], button:has-text('Login')")
                page.wait_for_timeout(3000)

        # If still on login page or redirected to registration
        if page.is_visible("text=Register") or page.is_visible("a:has-text('New User')"):
            logger.info("User account not found on portal. Triggering Auto-Registration...")
            if page.is_visible("a:has-text('New User')"):
                page.click("a:has-text('New User')")
            elif page.is_visible("a:has-text('Register')"):
                page.click("a:has-text('Register')")

            page.wait_for_timeout(2000)

            # Auto-fill portal sign-up form
            if page.is_visible("input[name*='name']"):
                page.fill("input[name*='name']", user_info.get("full_name", "Citizen User"))
            if page.is_visible("input[name*='email']"):
                page.fill("input[name*='email']", user_info.get("email", ""))
            if page.is_visible("input[name*='mobile']"):
                page.fill("input[name*='mobile']", user_info.get("phone", ""))
            if page.is_visible("input[name*='pincode']"):
                page.fill("input[name*='pincode']", user_info.get("pincode", "380026"))
            if page.is_visible("textarea[name*='address']"):
                page.fill("textarea[name*='address']", user_info.get("address", "Ahmedabad, Gujarat"))

            # Submit registration
            self._solve_portal_captcha(page)
            if page.is_visible("button:has-text('Submit'), input[value='Register']"):
                page.click("button:has-text('Submit'), input[value='Register']")
                page.wait_for_timeout(3000)

    def _navigate_to_request_form(self, page: Page, portal_config: Dict[str, Any]):
        """
        Navigates directly to the File RTI Request page.
        """
        request_selectors = [
            "a:has-text('Submit Request')", "a:has-text('File RTI')",
            "a:has-text('Apply Online')", "button:has-text('File Request')",
            "a[href*='request']", "a[href*='file']"
        ]
        for sel in request_selectors:
            if page.is_visible(sel):
                page.click(sel)
                page.wait_for_timeout(2000)
                break

    def _fill_rti_application_form(
        self,
        page: Page,
        user_info: Dict[str, Any],
        rti_text: str,
        department: str,
        file_path: Optional[str] = None
    ):
        """
        Fills all standard state RTI form inputs.
        """
        # Department Selection
        dept_dropdown = page.query_selector("select[name*='dept'], select[name*='authority'], select[id*='dept']")
        if dept_dropdown:
            options = page.eval_on_selector_all("select[name*='dept'] option", "opts => opts.map(o => o.text)")
            for opt in options:
                if department.lower() in opt.lower() or "municipal" in opt.lower():
                    dept_dropdown.select_option(label=opt)
                    break

        # User Personal Info
        if page.is_visible("input[name*='name']"):
            page.fill("input[name*='name']", user_info.get("full_name", ""))
        if page.is_visible("input[name*='email']"):
            page.fill("input[name*='email']", user_info.get("email", ""))
        if page.is_visible("input[name*='mobile']"):
            page.fill("input[name*='mobile']", user_info.get("phone", ""))
        if page.is_visible("textarea[name*='address']"):
            page.fill("textarea[name*='address']", user_info.get("address", ""))
        if page.is_visible("input[name*='pincode']"):
            page.fill("input[name*='pincode']", user_info.get("pincode", "380026"))

        # RTI Text Injection
        rti_text_area = page.query_selector("textarea[name*='text'], textarea[name*='rti'], textarea[name*='request'], textarea[id*='rti']")
        if rti_text_area:
            rti_text_area.fill(rti_text)

        # File Attachment
        if file_path and page.is_visible("input[type='file']"):
            page.set_input_files("input[type='file']", file_path)

    def _solve_portal_captcha(self, page: Page):
        """
        Locates CAPTCHA image and uses local OCR / AI Vision to auto-solve.
        """
        captcha_img = page.query_selector("img[src*='captcha'], img[id*='captcha'], img[alt*='captcha']")
        captcha_input = page.query_selector("input[name*='captcha'], input[id*='captcha']")

        if captcha_img and captcha_input:
            try:
                img_bytes = captcha_img.screenshot()
                solved_text = self.captcha_solver.solve(img_bytes)
                if solved_text:
                    captcha_input.fill(solved_text)
                    logger.info(f"Auto-solved CAPTCHA: '{solved_text}'")
            except Exception as e:
                logger.warning(f"CAPTCHA solving attempt skipped: {e}")