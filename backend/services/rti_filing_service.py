"""
RTI PORTAL FILING SERVICE (Visual Debug Mode Enabled)
=====================================================
Automates Central RTI filing. 
If running locally, opens visible browser and bypasses proxy.
"""

import asyncio
import base64
import io
import os
import re
import gc
from typing import Dict, Optional, Any
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
from playwright.sync_api import sync_playwright, Page
import structlog

from config.settings import settings

logger = structlog.get_logger()

CHROMIUM_LOW_MEM_FLAGS = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-accelerated-2d-canvas',
    '--no-first-run',
    '--no-zygote',
    '--disable-gpu',
]


class CaptchaSolver:
    def __init__(self):
        self._easyocr_reader = None

    def solve(self, captcha_image_bytes: bytes, attempt: int = 1) -> Optional[str]:
        result = self._try_tesseract(captcha_image_bytes)
        if result and len(result) >= 4: return result

        processed = self._preprocess_captcha(captcha_image_bytes)
        result = self._try_tesseract(processed)
        if result and len(result) >= 4: return result

        result = self._try_easyocr(captcha_image_bytes)
        if result and len(result) >= 4: return result
        return None

    def _try_tesseract(self, image_bytes: bytes) -> Optional[str]:
        try:
            import pytesseract
            image = Image.open(io.BytesIO(image_bytes)).convert('L')
            image = image.point(lambda x: 0 if x < 128 else 255)
            text = pytesseract.image_to_string(image, config='--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text.strip())
            return cleaned if cleaned else None
        except Exception: return None

    def _try_easyocr(self, image_bytes: bytes) -> Optional[str]:
        try:
            import easyocr, numpy as np
            if self._easyocr_reader is None:
                self._easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            image = Image.open(io.BytesIO(image_bytes))
            results = self._easyocr_reader.readtext(np.array(image))
            if results:
                text = ''.join([r[1] for r in results])
                return re.sub(r'[^a-zA-Z0-9]', '', text)
        except Exception: return None
        return None

    def _preprocess_captcha(self, image_bytes: bytes) -> bytes:
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('L')
            image = ImageEnhance.Contrast(image).enhance(2.0)
            image = ImageEnhance.Sharpness(image).enhance(2.0)
            image = image.point(lambda x: 0 if x < 140 else 255)
            image = image.filter(ImageFilter.MedianFilter(size=3))
            width, height = image.size
            image = image.resize((width * 2, height * 2), Image.LANCZOS)
            buf = io.BytesIO()
            image.save(buf, format='PNG')
            return buf.getvalue()
        except Exception: return image_bytes


class PortalFormMapper:
    MINISTRY_MAPPING: Dict[str, Dict[str, str]] = {
        "municipal_corporation": {"ministry": "Ministry of Housing and Urban Affairs", "public_authority": ""},
        "pwd": {"ministry": "Ministry of Road Transport and Highways", "public_authority": "Ministry of Road Transport and Highways"},
        "nhai": {"ministry": "Ministry of Road Transport and Highways", "public_authority": "National Highways Authority of India"},
        "water_board": {"ministry": "Ministry of Jal Shakti", "public_authority": "Department of Drinking Water and Sanitation"},
        "electricity_board": {"ministry": "Ministry of Power", "public_authority": "Ministry of Power"},
        "general": {"ministry": "Ministry of Personnel, Public Grievances and Pensions", "public_authority": "Department of Personnel and Training"},
    }
    STATE_VALUES: Dict[str, str] = {"gujarat": "Gujarat", "delhi": "Delhi", "maharashtra": "Maharashtra"}
    GENDER_VALUES = {"male": "Male", "female": "Female", "transgender": "Transgender"}
    EDUCATION_VALUES = {"graduate": "Graduate & Above", "primary": "Primary", "literate": "Literate"}

    @classmethod
    def get_ministry_for_department(cls, department_type: str) -> Dict[str, str]:
        return cls.MINISTRY_MAPPING.get(department_type, cls.MINISTRY_MAPPING["general"])
    @classmethod
    def get_state_value(cls, state: str) -> str:
        state_key = (state or "").lower().replace(" ", "_").strip()
        return cls.STATE_VALUES.get(state_key, (state or "").title())


class RTIFilingService:
    CENTRAL_PORTAL_URL = "https://rtionline.gov.in"
    REQUEST_URL = "https://rtionline.gov.in/request/request.php"
    STATUS_URL = "https://rtionline.gov.in/request/status.php"

    def __init__(self):
        self.captcha_solver = CaptchaSolver()
        self.form_mapper = PortalFormMapper()

    async def file_on_central_portal(self, *args, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self._file_sync, *args, **kwargs)

    def _file_sync(
        self, applicant_name, applicant_gender, applicant_address,
        applicant_pincode, applicant_state, applicant_phone,
        applicant_email, applicant_education, is_bpl,
        is_life_liberty, department_type, rti_text,
        supporting_doc_path=None, area_type="urban"
    ) -> Dict[str, Any]:
        
        screenshots = []
        steps_completed = []
        is_local_debug = settings.DEBUG

        indian_proxy = None
        if not is_local_debug:
            try:
                from services.proxy_service import get_indian_proxy_sync
                indian_proxy = get_indian_proxy_sync()
            except Exception: pass

        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "headless": not is_local_debug,
                    "args": CHROMIUM_LOW_MEM_FLAGS if not is_local_debug else [],
                    "slow_mo": 50 if is_local_debug else 0
                }
                if indian_proxy and not is_local_debug:
                    launch_kwargs["proxy"] = indian_proxy

                logger.info("central_adapter_launching", visual_mode=is_local_debug)

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(viewport={'width': 1280, 'height': 720})
                page = context.new_page()
                page.set_default_timeout(45000)

                page.goto(self.REQUEST_URL, wait_until="domcontentloaded", timeout=45000)
                steps_completed.append("navigated_to_portal")

                try:
                    cb = page.locator('input[type="checkbox"]').first
                    if cb.is_visible(timeout=3000):
                        cb.check()
                        page.locator('input[type="submit"], button[type="submit"]').first.click()
                        page.wait_for_load_state("domcontentloaded")
                except Exception: pass

                ministry_info = self.form_mapper.get_ministry_for_department(department_type)
                try:
                    m_sel = page.locator('select[name="m_id"], select#m_id').first
                    m_sel.wait_for(state="visible", timeout=3000)
                    m_sel.select_option(label=ministry_info["ministry"])
                except Exception: pass

                try:
                    a_sel = page.locator('select[name="pa_id"], select#pa_id').first
                    if a_sel.is_visible(timeout=2000):
                        a_sel.select_option(label=ministry_info["public_authority"])
                except Exception: pass

                if applicant_is_life_liberty:
                    page.locator('input[type="radio"][value="Yes"], input[type="radio"][value="1"]').first.check()
                else:
                    page.locator('input[type="radio"][value="No"], input[type="radio"][value="0"]').first.check()

                fields = [
                    ('input[name="name"]', applicant_name),
                    ('textarea[name="address"], input[name="address"]', applicant_address),
                    ('input[name="pincode"]', applicant_pincode),
                    ('input[name="phone"], input[name="mobile"]', applicant_phone),
                    ('input[name="email"]', applicant_email),
                ]
                for sel, val in fields:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=1000): el.fill(val or "")
                    except Exception: pass

                if is_bpl:
                    page.locator('input[name="bpl"][value="Yes"]').first.check()
                else:
                    page.locator('input[name="bpl"][value="No"]').first.check()

                try:
                    txt = page.locator('textarea[name="request_text"], textarea#RTIText').first
                    if txt.is_visible(timeout=2000): txt.fill((rti_text or "")[:3000])
                except Exception: pass

                captcha_solved = False
                for attempt in range(1, 4):
                    try:
                        c_img = page.locator('img[src*="captcha"]').first
                        if c_img.is_visible(timeout=3000):
                            c_bytes = c_img.screenshot()
                            c_text = self.captcha_solver.solve(c_bytes, attempt)
                            if c_text:
                                page.locator('input[name="captcha"], input[name="security_code"]').first.fill(c_text)
                                captcha_solved = True
                                break
                    except Exception: pass
                
                if not captcha_solved:
                    context.close()
                    browser.close()
                    gc.collect()
                    return {"success": False, "requires_manual_captcha": True, "error": "CAPTCHA failed."}

                if is_local_debug:
                    import time
                    time.sleep(5)

                page.locator('input[type="submit"][value*="Submit"], button[type="submit"]').first.click()
                try: page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception: pass

                page_text = page.inner_text('body')
                current_url = page.url

                reg_match = re.search(r'(MOIAF/[A-Z]/[A-Z]/\d{2}/\d+)', page_text)
                reg_number = reg_match.group(1) if reg_match else None

                context.close()
                browser.close()
                gc.collect()

                if reg_number:
                    return {"success": True, "registration_number": reg_number, "message": f"Filed! Reg No: {reg_number}"}

                is_payment = any(k in current_url.lower() for k in ["payment", "pay", "sbi", "billdesk"])
                if is_payment:
                    return {"success": True, "requires_payment": True, "payment_url": current_url}

                return {"success": True, "payment_url": self.CENTRAL_PORTAL_URL}

        except Exception as e:
            logger.error("central_filing_error", error=str(e))
            gc.collect()
            return {"success": False, "error": str(e), "payment_url": self.CENTRAL_PORTAL_URL}

    async def check_status_on_portal(self, registration_number: str, email: str) -> Dict[str, Any]:
        return await asyncio.to_thread(self._check_status_sync, registration_number, email)

    def _check_status_sync(self, registration_number: str, email: str) -> Dict[str, Any]:
        return {"success": False, "error": "Not checking online directly during debug phase"}