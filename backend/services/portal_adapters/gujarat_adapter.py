"""
GUJARAT STATE RTI PORTAL ADAPTER (Memory-Optimized Sync Engine)
=====================================================================
Portal: https://rti.gujarat.gov.in
Runs via asyncio.to_thread to be 100% immune to Windows event loop bugs.
Memory optimized to run under 180MB for Render Free Tier.
Uses Indian Proxy so Render (Singapore) bypasses NIC firewall blocks.
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
        self.portal_url = "https://rti.gujarat.gov.in"
        self.submit_url = "https://rti.gujarat.gov.in/Request/Request.aspx"
        self.status_url = "https://rti.gujarat.gov.in/Request/Status.aspx"
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
        return state.lower().strip() in ["gujarat", "gj"]

    def get_department_options(self, department_type: str, city: str = "") -> Dict[str, str]:
        dept_data = self._department_map.get(department_type, self._department_map["general"])
        city_lower = city.lower().strip()
        if city_lower in dept_data:
            return dept_data[city_lower]
        return dept_data.get("default", {"department": "General Administration Department", "authority": "General Administration Department"})

    async def file_rti(self, applicant: ApplicantDetails, rti_request: RTIRequestDetails, page=None) -> FilingResult:
        """Run filing synchronously in a background thread."""
        return await asyncio.to_thread(self._file_sync, applicant, rti_request)

    def _file_sync(self, applicant: ApplicantDetails, rti_request: RTIRequestDetails) -> FilingResult:
        from services.rti_filing_service import CaptchaSolver
        
        # Fetch Indian proxy
        from services.proxy_service import get_indian_proxy_sync
        indian_proxy = get_indian_proxy_sync()
        
        screenshots = []
        steps = []
        captcha_solver = CaptchaSolver()

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
                page.set_default_timeout(35000)

                # 1. Navigate
                page.goto(self.submit_url, wait_until="domcontentloaded")
                steps.append(FilingStep.NAVIGATE.value)

                # 2. Select Department
                dept_opts = self.get_department_options(rti_request.department_type, applicant.city)
                self._sync_select(page, "select#ddlDepartment, select[name$='ddlDepartment']", dept_opts["department"])
                steps.append(FilingStep.SELECT_DEPT.value)

                # 3. Select Authority
                self._sync_select(page, "select#ddlAuthority, select[name$='ddlAuthority']", dept_opts["authority"])
                steps.append(FilingStep.SELECT_AUTHORITY.value)

                # 4. Life/Liberty
                if applicant.is_life_liberty:
                    self._sync_click(page, "input[id$='rdoLifeYes'], input[value='Yes'][name*='Life']")
                else:
                    self._sync_click(page, "input[id$='rdoLifeNo'], input[value='No'][name*='Life']")
                steps.append(FilingStep.LIFE_LIBERTY.value)

                # 5. Fill Details
                self._sync_fill(page, "input[id$='txtName'], input[name$='txtName']", applicant.name)
                self._sync_select(page, "select[id$='ddlGender'], select[name$='ddlGender']", applicant.gender.title())
                self._sync_fill(page, "textarea[id$='txtAddress'], textarea[name$='txtAddress']", applicant.address)
                self._sync_fill(page, "input[id$='txtPincode'], input[name$='txtPincode']", applicant.pincode)
                self._sync_select(page, "select[id$='ddlState'], select[name$='ddlState']", "Gujarat")
                if applicant.district:
                    self._sync_select(page, "select[id$='ddlDistrict'], select[name$='ddlDistrict']", applicant.district.title())
                
                self._sync_select(page, "select[id$='ddlStatus'], select[name$='ddlStatus']", "Urban" if applicant.area_type == "urban" else "Rural")
                self._sync_fill(page, "input[id$='txtPhone'], input[name$='txtPhone']", applicant.phone)
                self._sync_fill(page, "input[id$='txtMobile'], input[name$='txtMobile']", applicant.phone)
                self._sync_fill(page, "input[id$='txtEmail'], input[name$='txtEmail']", applicant.email)
                self._sync_select(page, "select[id$='ddlCountry'], select[name$='ddlCountry']", "Indian")

                if applicant.is_bpl:
                    self._sync_click(page, "input[id$='rdoBPLYes'], input[value='Yes'][name*='BPL']")
                else:
                    self._sync_click(page, "input[id$='rdoBPLNo'], input[value='No'][name*='BPL']")
                steps.append("applicant_details_filled")

                # 6. Fill RTI Text
                self._sync_fill(page, "textarea[id$='txtRTI'], textarea[name$='txtRTI'], textarea[id$='txtRequest']", rti_request.rti_text[:self.max_text_length])
                steps.append(FilingStep.FILL_TEXT.value)

                # 7. CAPTCHA
                captcha_solved = False
                for attempt in range(1, 4):
                    try:
                        c_img = page.locator("img[id$='imgCaptcha'], img[src*='captcha']").first
                        if c_img.is_visible(timeout=3000):
                            c_bytes = c_img.screenshot()
                            c_text = captcha_solver.solve(c_bytes, attempt)
                            if c_text:
                                self._sync_fill(page, "input[id$='txtCaptcha'], input[name$='txtCaptcha'], input[id$='txtSecurityCode']", c_text)
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
                        error="CAPTCHA solving failed.",
                        portal_url=self.portal_url,
                        portal_name=self.portal_name
                    )

                # 8. Submit
                self._sync_click(page, "input[id$='btnSubmit'], input[type='submit'][value*='Submit']")
                page.wait_for_load_state("domcontentloaded", timeout=12000)
                steps.append(FilingStep.SUBMIT.value)

                page_text = page.inner_text("body")
                current_url = page.url

                # Check Registration Number
                reg_match = re.search(r'(GUJ[/-][A-Z]+[/-]\d{4}[/-]\d+)', page_text)
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

                is_payment = any(k in current_url.lower() for k in ["payment", "pay", "sbi", "treasury", "epay"])
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
            return FilingResult(success=False, steps_completed=steps, error=str(e), portal_name=self.portal_name, portal_url=self.portal_url, payment_url=self.portal_url)

    async def check_status(self, registration_number: str, email: str, page=None) -> StatusResult:
        return await asyncio.to_thread(self._check_status_sync, registration_number, email)

    def _check_status_sync(self, registration_number: str, email: str) -> StatusResult:
        from services.proxy_service import get_indian_proxy_sync
        indian_proxy = get_indian_proxy_sync()
        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "headless": True,
                    "args": CHROMIUM_LOW_MEM_FLAGS,
                }
                if indian_proxy:
                    launch_kwargs["proxy"] = indian_proxy

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(viewport={'width': 1280, 'height': 720})
                page = context.new_page()
                page.goto(self.status_url, wait_until="domcontentloaded")
                self._sync_fill(page, "input[id$='txtRegNo']", registration_number)
                self._sync_fill(page, "input[id$='txtEmail']", email)
                self._sync_click(page, "input[id$='btnSearch']")
                page.wait_for_load_state("domcontentloaded")
                page_text = page.inner_text("body")
                
                context.close()
                browser.close()
                gc.collect()

                status = "pending"
                if "disposed" in page_text.lower():
                    status = "response_received"
                return StatusResult(success=True, registration_number=registration_number, status=status)
        except Exception as e:
            gc.collect()
            return StatusResult(success=False, error=str(e))

    # Helper sync methods
    def _sync_fill(self, page: Page, selector: str, value: str):
        for sel in selector.split(","):
            try:
                el = page.locator(sel.strip()).first
                if el.is_visible(timeout=1000):
                    el.fill(value)
                    return
            except Exception:
                pass

    def _sync_select(self, page: Page, selector: str, value: str):
        for sel in selector.split(","):
            try:
                el = page.locator(sel.strip()).first
                if el.is_visible(timeout=1000):
                    try:
                        el.select_option(label=value)
                        return
                    except Exception:
                        for opt in el.locator("option").all():
                            if value.lower() in (opt.text_content() or "").lower():
                                el.select_option(value=opt.get_attribute("value"))
                                return
            except Exception:
                pass

    def _sync_click(self, page: Page, selector: str):
        for sel in selector.split(","):
            try:
                el = page.locator(sel.strip()).first
                if el.is_visible(timeout=1000):
                    el.click()
                    return
            except Exception:
                pass