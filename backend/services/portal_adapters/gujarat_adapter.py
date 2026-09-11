"""
GUJARAT STATE RTI PORTAL ADAPTER (Updated Active URL)
=====================================================
Active Portal: https://onlinerti.gujarat.gov.in/rti_portal/
"""

import asyncio
import re
import base64
import gc
from typing import Dict, Optional, List, Any
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

from .base_adapter import (
    BasePortalAdapter, FilingResult, StatusResult,
    ApplicantDetails, RTIRequestDetails, FilingStep
)
import structlog

logger = structlog.get_logger()

CHROMIUM_LOW_MEM_FLAGS = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-accelerated-2d-canvas',
    '--no-first-run',
    '--no-zygote',
    '--single-process',
    '--disable-gpu',
    '--disable-software-rasterizer',
    '--js-flags="--max-old-space-size=128"',
]


class GujaratPortalAdapter(BasePortalAdapter):
    """Adapter for Gujarat State RTI Portal using synchronous playwright."""

    def __init__(self):
        super().__init__()
        self.portal_name = "Gujarat State RTI Portal"
        self.portal_url = "https://onlinerti.gujarat.gov.in/rti_portal/"
        self.submit_url = "https://onlinerti.gujarat.gov.in/rti_portal/"
        self.status_url = "https://onlinerti.gujarat.gov.in/rti_portal/"
        self.max_text_length = 3000

        self._department_map = {
            "municipal_corporation": {
                "ahmedabad": {"department": "Urban Development and Urban Housing Department", "authority": "Ahmedabad Municipal Corporation"},
                "surat": {"department": "Urban Development and Urban Housing Department", "authority": "Surat Municipal Corporation"},
                "vadodara": {"department": "Urban Development and Urban Housing Department", "authority": "Vadodara Municipal Corporation"},
                "rajkot": {"department": "Urban Development and Urban Housing Department", "authority": "Rajkot Municipal Corporation"},
                "default": {"department": "Urban Development and Urban Housing Department", "authority": "Directorate of Municipal Administration"},
            },
            "pwd": {"default": {"department": "Roads and Buildings Department", "authority": "Roads and Buildings Department"}},
            "water_board": {"default": {"department": "Water Supply and Kalpasar Department", "authority": "Gujarat Water Supply and Sewerage Board"}},
            "electricity_board": {"default": {"department": "Energy and Petrochemicals Department", "authority": "Gujarat Urja Vikas Nigam Limited"}},
            "education_department": {"default": {"department": "Education Department", "authority": "Directorate of Primary Education"}},
            "health_department": {"default": {"department": "Health and Family Welfare Department", "authority": "Directorate of Health and Family Welfare"}},
            "police_department": {"default": {"department": "Home Department", "authority": "Director General of Police"}},
            "revenue_department": {"default": {"department": "Revenue Department", "authority": "Collector Office"}},
            "panchayat": {"default": {"department": "Panchayat, Rural Housing and Rural Development Department", "authority": "District Panchayat"}},
            "general": {"default": {"department": "General Administration Department", "authority": "General Administration Department"}},
        }

    def supports_state(self, state: str) -> bool:
        return (state or "").lower().strip() in ["gujarat", "gj"]

    def get_department_options(self, department_type: str, city: str = "") -> Dict[str, str]:
        dept_data = self._department_map.get(department_type, self._department_map["general"])
        city_lower = (city or "").lower().strip()
        if city_lower in dept_data:
            return dept_data[city_lower]
        return dept_data.get("default", {"department": "General Administration Department", "authority": "General Administration Department"})

    async def file_rti(self, applicant: ApplicantDetails, rti_request: RTIRequestDetails, page=None) -> FilingResult:
        """Run filing synchronously in a background thread."""
        return await asyncio.to_thread(self._file_sync, applicant, rti_request)

    def _get_proxy(self):
        try:
            from services.proxy_service import get_indian_proxy_sync
            return get_indian_proxy_sync()
        except Exception:
            return None

    def _file_sync(self, applicant: ApplicantDetails, rti_request: RTIRequestDetails) -> FilingResult:
        from services.rti_filing_service import CaptchaSolver
        
        screenshots = []
        steps = []
        captcha_solver = CaptchaSolver()
        indian_proxy = self._get_proxy()

        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "headless": True,
                    "args": CHROMIUM_LOW_MEM_FLAGS,
                }
                if indian_proxy:
                    launch_kwargs["proxy"] = indian_proxy
                    logger.info("gujarat_adapter_launching_with_indian_proxy", proxy=indian_proxy)

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()
                page.set_default_timeout(45000)

                # 1. Navigate
                page.goto(self.submit_url, wait_until="domcontentloaded", timeout=45000)
                steps.append(FilingStep.NAVIGATE.value)

                # Look for "Submit Request" or "File RTI" button if on landing page
                try:
                    submit_link = page.locator("a:has-text('Submit Request'), button:has-text('Submit Request'), a:has-text('Apply')").first
                    if submit_link.is_visible(timeout=3000):
                        submit_link.click()
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass

                # 2. Select Department
                dept_opts = self.get_department_options(rti_request.department_type, applicant.city)
                self._sync_select(page, "select#ddlDepartment, select[name*='Department'], select[id*='Department']", dept_opts["department"])
                steps.append(FilingStep.SELECT_DEPT.value)

                # 3. Select Authority
                self._sync_select(page, "select#ddlAuthority, select[name*='Authority'], select[id*='Authority']", dept_opts["authority"])
                steps.append(FilingStep.SELECT_AUTHORITY.value)

                # 4. Life/Liberty
                if applicant.is_life_liberty:
                    self._sync_click(page, "input[id*='LifeYes'], input[value='Yes'][name*='Life']")
                else:
                    self._sync_click(page, "input[id*='LifeNo'], input[value='No'][name*='Life']")
                steps.append(FilingStep.LIFE_LIBERTY.value)

                # 5. Fill Applicant Details
                self._sync_fill(page, "input[id*='txtName'], input[name*='Name']", applicant.name)
                self._sync_select(page, "select[id*='Gender'], select[name*='Gender']", (applicant.gender or "male").title())
                self._sync_fill(page, "textarea[id*='Address'], textarea[name*='Address']", applicant.address)
                self._sync_fill(page, "input[id*='Pincode'], input[name*='Pincode']", applicant.pincode)
                self._sync_select(page, "select[id*='State'], select[name*='State']", "Gujarat")
                if applicant.district:
                    self._sync_select(page, "select[id*='District'], select[name*='District']", applicant.district.title())
                
                self._sync_select(page, "select[id*='Status'], select[name*='Status']", "Urban" if (applicant.area_type or "urban") == "urban" else "Rural")
                self._sync_fill(page, "input[id*='Phone'], input[name*='Phone']", applicant.phone)
                self._sync_fill(page, "input[id*='Mobile'], input[name*='Mobile']", applicant.phone)
                self._sync_fill(page, "input[id*='Email'], input[name*='Email']", applicant.email)
                self._sync_select(page, "select[id*='Country'], select[name*='Country']", "Indian")

                if applicant.is_bpl:
                    self._sync_click(page, "input[id*='BPLYes'], input[value='Yes'][name*='BPL']")
                else:
                    self._sync_click(page, "input[id*='BPLNo'], input[value='No'][name*='BPL']")
                steps.append("applicant_details_filled")

                # 6. Fill RTI Text
                self._sync_fill(page, "textarea[id*='RTI'], textarea[name*='RTI'], textarea[id*='Request'], textarea[name*='text']", (rti_request.rti_text or "")[:self.max_text_length])
                steps.append(FilingStep.FILL_TEXT.value)

                # 7. CAPTCHA
                captcha_solved = False
                for attempt in range(1, 4):
                    try:
                        c_img = page.locator("img[id*='Captcha'], img[src*='captcha'], img[alt*='captcha']").first
                        if c_img.is_visible(timeout=3000):
                            c_bytes = c_img.screenshot()
                            c_text = captcha_solver.solve(c_bytes, attempt)
                            if c_text:
                                self._sync_fill(page, "input[id*='Captcha'], input[name*='Captcha'], input[id*='SecurityCode']", c_text)
                                captcha_solved = True
                                break
                    except Exception:
                        pass
                
                if not captcha_solved:
                    context.close()
                    browser.close()
                    gc.collect()
                    return FilingResult(
                        success=False, 
                        requires_manual_captcha=True, 
                        steps_completed=steps, 
                        error="CAPTCHA solving failed on Gujarat portal.",
                        portal_url=self.portal_url,
                        portal_name=self.portal_name
                    )

                # 8. Submit
                self._sync_click(page, "input[id*='btnSubmit'], input[type='submit'][value*='Submit'], button[type='submit']")
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                steps.append(FilingStep.SUBMIT.value)

                page_text = page.inner_text("body")
                current_url = page.url

                reg_match = re.search(r'(GUJ[/-][A-Z0-9]+[/-]\d{4}[/-]\d+)', page_text, re.IGNORECASE)
                reg_number = reg_match.group(1) if reg_match else None

                context.close()
                browser.close()
                gc.collect()

                if reg_number:
                    return FilingResult(
                        success=True, registration_number=reg_number, payment_amount=0 if applicant.is_bpl else 10.0,
                        steps_completed=steps, message=f"RTI filed on Gujarat Portal! Reg No: {reg_number}",
                        portal_name=self.portal_name, portal_url=self.portal_url
                    )

                is_payment = any(k in current_url.lower() for k in ["payment", "pay", "sbi", "treasury", "epay", "billdesk"])
                if is_payment or "payment" in page_text.lower()[:500]:
                    return FilingResult(
                        success=True, requires_payment=True, payment_url=current_url, payment_amount=10.0,
                        steps_completed=steps, message="Form submitted on Gujarat Portal. Complete ₹10 payment.",
                        portal_name=self.portal_name, portal_url=self.portal_url
                    )

                return FilingResult(
                    success=True, steps_completed=steps,
                    message=f"Form submitted. Check email {applicant.email} for confirmation.",
                    portal_name=self.portal_name, portal_url=self.portal_url, payment_url=self.portal_url
                )

        except Exception as e:
            logger.error("gujarat_filing_error", error=str(e))
            gc.collect()
            return FilingResult(
                success=False,
                steps_completed=steps,
                error=str(e),
                portal_name=self.portal_name,
                portal_url=self.portal_url,
                payment_url=self.portal_url,
                message=(
                    f"Gujarat State RTI Portal could not be reached ({str(e)}). "
                    f"Your draft is saved. Open {self.portal_url} and paste your draft, "
                    f"or retry auto-filing in a few minutes."
                )
            )

    async def check_status(self, registration_number: str, email: str, page=None) -> StatusResult:
        return await asyncio.to_thread(self._check_status_sync, registration_number, email)

    def _check_status_sync(self, registration_number: str, email: str) -> StatusResult:
        indian_proxy = self._get_proxy()
        try:
            with sync_playwright() as p:
                launch_kwargs = {"headless": True, "args": CHROMIUM_LOW_MEM_FLAGS}
                if indian_proxy:
                    launch_kwargs["proxy"] = indian_proxy

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(viewport={'width': 1280, 'height': 720})
                page = context.new_page()
                page.set_default_timeout(45000)
                page.goto(self.status_url, wait_until="domcontentloaded", timeout=45000)

                self._sync_fill(page, "input[id*='RegNo'], input[name*='RegNo']", registration_number)
                self._sync_fill(page, "input[id*='Email'], input[name*='Email']", email)
                self._sync_click(page, "input[id*='btnSearch'], input[type='submit']")
                
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass

                page_text = page.inner_text("body")
                context.close()
                browser.close()
                gc.collect()

                status = "pending"
                lower = page_text.lower()
                if "disposed" in lower or "replied" in lower:
                    status = "response_received"
                elif "transferred" in lower:
                    status = "transferred"
                elif "rejected" in lower:
                    status = "rejected"

                return StatusResult(success=True, registration_number=registration_number, status=status)
        except Exception as e:
            gc.collect()
            return StatusResult(success=False, error=str(e))

    def _sync_fill(self, page: Page, selector: str, value: str):
        for sel in selector.split(","):
            try:
                el = page.locator(sel.strip()).first
                if el.is_visible(timeout=1500):
                    el.fill(value or "")
                    return
            except Exception:
                pass

    def _sync_select(self, page: Page, selector: str, value: str):
        for sel in selector.split(","):
            try:
                el = page.locator(sel.strip()).first
                if el.is_visible(timeout=1500):
                    try:
                        el.select_option(label=value)
                        return
                    except Exception:
                        for opt in el.locator("option").all():
                            text = opt.text_content() or ""
                            if value.lower() in text.lower():
                                v = opt.get_attribute("value")
                                if v is not None:
                                    el.select_option(value=v)
                                    return
            except Exception:
                pass

    def _sync_click(self, page: Page, selector: str):
        for sel in selector.split(","):
            try:
                el = page.locator(sel.strip()).first
                if el.is_visible(timeout=1500):
                    el.click()
                    return
            except Exception:
                pass