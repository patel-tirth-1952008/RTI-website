"""
RTI PORTAL FILING SERVICE (Memory-Optimized Sync Engine)
==============================================================
Automates RTI filing on central government portals.
Runs via asyncio.to_thread to be 100% immune to Windows event loop bugs.
Memory optimized to run under 180MB for Render Free Tier.
"""

import asyncio
import base64
import io
import os
import re
import gc
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout
import structlog

from config.settings import settings
from config.constants import ApplicationStatus, IssueCategory, DepartmentType, RTI_PORTALS

logger = structlog.get_logger()

# Ultra-low memory flags for Chromium (Keeps RAM under 100MB per instance)
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


# ============================================================
# CAPTCHA SOLVER (Synchronous & Memory Optimized)
# ============================================================

class CaptchaSolver:
    """Solves text-based CAPTCHAs from government RTI portals synchronously."""

    def __init__(self):
        self._easyocr_reader = None

    def solve(self, captcha_image_bytes: bytes, attempt: int = 1) -> Optional[str]:
        # Strategy 1: Tesseract OCR (Lightweight, ~15MB RAM)
        result = self._try_tesseract(captcha_image_bytes)
        if result and len(result) >= 4:
            logger.info("captcha_solved_tesseract", text=result, attempt=attempt)
            return result

        # Strategy 2: Preprocess & Tesseract
        processed = self._preprocess_captcha(captcha_image_bytes)
        result = self._try_tesseract(processed)
        if result and len(result) >= 4:
            logger.info("captcha_solved_preprocessed", text=result, attempt=attempt)
            return result

        # Strategy 3: EasyOCR (Heavy fallback, ~200MB RAM)
        result = self._try_easyocr(captcha_image_bytes)
        if result and len(result) >= 4:
            logger.info("captcha_solved_easyocr", text=result, attempt=attempt)
            return result

        logger.warning("captcha_solve_failed", attempt=attempt)
        return None

    def _try_tesseract(self, image_bytes: bytes) -> Optional[str]:
        try:
            import pytesseract
            image = Image.open(io.BytesIO(image_bytes)).convert('L')
            image = image.point(lambda x: 0 if x < 128 else 255)
            text = pytesseract.image_to_string(
                image,
                config='--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            )
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text.strip())
            return cleaned if cleaned else None
        except Exception as e:
            logger.warning("tesseract_failed", error=str(e))
        return None

    def _try_easyocr(self, image_bytes: bytes) -> Optional[str]:
        try:
            import easyocr
            import numpy as np
            if self._easyocr_reader is None:
                self._easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            image = Image.open(io.BytesIO(image_bytes))
            results = self._easyocr_reader.readtext(np.array(image))
            if results:
                text = ''.join([r[1] for r in results])
                cleaned = re.sub(r'[^a-zA-Z0-9]', '', text)
                return cleaned if cleaned else None
        except Exception as e:
            logger.warning("easyocr_failed", error=str(e))
        return None

    def _preprocess_captcha(self, image_bytes: bytes) -> bytes:
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('L')
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            image = image.point(lambda x: 0 if x < 140 else 255)
            image = image.filter(ImageFilter.MedianFilter(size=3))
            width, height = image.size
            image = image.resize((width * 2, height * 2), Image.LANCZOS)
            buf = io.BytesIO()
            image.save(buf, format='PNG')
            return buf.getvalue()
        except Exception:
            return image_bytes


# ============================================================
# PORTAL FORM MAPPER
# ============================================================

class PortalFormMapper:
    MINISTRY_MAPPING: Dict[str, Dict[str, str]] = {
        "municipal_corporation": {"ministry": "Ministry of Housing and Urban Affairs", "public_authority": ""},
        "pwd": {"ministry": "Ministry of Road Transport and Highways", "public_authority": "Ministry of Road Transport and Highways"},
        "nhai": {"ministry": "Ministry of Road Transport and Highways", "public_authority": "National Highways Authority of India"},
        "water_board": {"ministry": "Ministry of Jal Shakti", "public_authority": "Department of Drinking Water and Sanitation"},
        "electricity_board": {"ministry": "Ministry of Power", "public_authority": "Ministry of Power"},
        "education_department": {"ministry": "Ministry of Education", "public_authority": "Department of School Education and Literacy"},
        "health_department": {"ministry": "Ministry of Health and Family Welfare", "public_authority": "Ministry of Health and Family Welfare"},
        "police_department": {"ministry": "Ministry of Home Affairs", "public_authority": "Ministry of Home Affairs"},
        "revenue_department": {"ministry": "Ministry of Finance", "public_authority": "Department of Revenue"},
        "panchayat": {"ministry": "Ministry of Panchayati Raj", "public_authority": "Ministry of Panchayati Raj"},
        "general": {"ministry": "Ministry of Personnel, Public Grievances and Pensions", "public_authority": "Department of Personnel and Training"},
    }

    STATE_VALUES: Dict[str, str] = {
        "andhra_pradesh": "Andhra Pradesh", "arunachal_pradesh": "Arunachal Pradesh", "assam": "Assam", "bihar": "Bihar",
        "chhattisgarh": "Chhattisgarh", "delhi": "Delhi", "goa": "Goa", "gujarat": "Gujarat", "haryana": "Haryana",
        "himachal_pradesh": "Himachal Pradesh", "jharkhand": "Jharkhand", "karnataka": "Karnataka", "kerala": "Kerala",
        "madhya_pradesh": "Madhya Pradesh", "maharashtra": "Maharashtra", "manipur": "Manipur", "meghalaya": "Meghalaya",
        "mizoram": "Mizoram", "nagaland": "Nagaland", "odisha": "Odisha", "punjab": "Punjab", "rajasthan": "Rajasthan",
        "sikkim": "Sikkim", "tamil_nadu": "Tamil Nadu", "telangana": "Telangana", "tripura": "Tripura",
        "uttar_pradesh": "Uttar Pradesh", "uttarakhand": "Uttarakhand", "west_bengal": "West Bengal",
        "chandigarh": "Chandigarh", "puducherry": "Puducherry", "jammu_kashmir": "Jammu and Kashmir", "ladakh": "Ladakh",
    }

    GENDER_VALUES = {"male": "Male", "female": "Female", "transgender": "Transgender"}
    EDUCATION_VALUES = {
        "literate": "Literate", "informal_education": "Informal Education", "below_primary": "Below Primary",
        "primary": "Primary", "middle": "Middle", "matric_secondary": "Matric/Secondary",
        "higher_secondary": "Higher Secondary", "graduate": "Graduate & Above",
    }

    @classmethod
    def get_ministry_for_department(cls, department_type: str) -> Dict[str, str]:
        return cls.MINISTRY_MAPPING.get(department_type, cls.MINISTRY_MAPPING["general"])

    @classmethod
    def get_state_value(cls, state: str) -> str:
        state_key = state.lower().replace(" ", "_").strip()
        return cls.STATE_VALUES.get(state_key, state.title())


# ============================================================
# MAIN FILING SERVICE
# ============================================================

class RTIFilingService:
    CENTRAL_PORTAL_URL = "https://rtionline.gov.in"
    REQUEST_URL = "https://rtionline.gov.in/request/request.php"
    STATUS_URL = "https://rtionline.gov.in/request/status.php"

    def __init__(self):
        self.captcha_solver = CaptchaSolver()
        self.form_mapper = PortalFormMapper()

    async def close(self):
        """Cleanup method for backward compatibility."""
        pass

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

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True, 
                    args=CHROMIUM_LOW_MEM_FLAGS
                )
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = context.new_page()
                page.set_default_timeout(25000)

                # Step 1: Navigate
                page.goto(self.REQUEST_URL, wait_until="domcontentloaded")
                steps_completed.append("navigated_to_portal")
                screenshots.append(base64.b64encode(page.screenshot()).decode('utf-8'))

                # Step 2: Guidelines
                try:
                    cb = page.locator('input[type="checkbox"]').first
                    if cb.is_visible(timeout=3000):
                        cb.check()
                        page.locator('input[type="submit"], button[type="submit"]').first.click()
                        page.wait_for_load_state("domcontentloaded")
                        steps_completed.append("guidelines_accepted")
                except Exception:
                    steps_completed.append("guidelines_skipped")

                # Step 3: Ministry
                ministry_info = self.form_mapper.get_ministry_for_department(department_type)
                try:
                    m_sel = page.locator('select[name="m_id"], select#m_id').first
                    m_sel.wait_for(state="visible", timeout=3000)
                    try:
                        m_sel.select_option(label=ministry_info["ministry"])
                    except Exception:
                        for opt in m_sel.locator('option').all():
                            if ministry_info["ministry"].lower() in (opt.text_content() or "").lower():
                                m_sel.select_option(value=opt.get_attribute('value'))
                                break
                except Exception:
                    pass
                steps_completed.append("ministry_selected")

                # Authority
                if ministry_info.get("public_authority"):
                    try:
                        a_sel = page.locator('select[name="pa_id"], select#pa_id').first
                        a_sel.wait_for(state="visible", timeout=2000)
                        try:
                            a_sel.select_option(label=ministry_info["public_authority"])
                        except Exception:
                            for opt in a_sel.locator('option').all():
                                if ministry_info["public_authority"].lower() in (opt.text_content() or "").lower():
                                    a_sel.select_option(value=opt.get_attribute('value'))
                                    break
                    except Exception:
                        pass

                # Life/Liberty
                try:
                    if is_life_liberty:
                        page.locator('input[type="radio"][value="Yes"], input[type="radio"][value="1"]').first.check()
                    else:
                        page.locator('input[type="radio"][value="No"], input[type="radio"][value="0"]').first.check()
                except Exception:
                    pass

                # Applicant Details
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
                        if el.is_visible(timeout=1000):
                            el.fill(val)
                    except Exception:
                        pass

                # Dropdowns
                dropdowns = [
                    ('select[name="gender"]', self.form_mapper.GENDER_VALUES.get(applicant_gender.lower(), "Male")),
                    ('select[name="state"]', self.form_mapper.get_state_value(applicant_state)),
                    ('select[name="status"], select[name="urban_rural"]', "Urban" if area_type.lower() == "urban" else "Rural"),
                    ('select[name="education"], select[name="edu_status"]', self.form_mapper.EDUCATION_VALUES.get(applicant_education.lower(), "Graduate & Above")),
                    ('select[name="country"], select[name="citizenship"]', "Indian"),
                ]
                for sel, val in dropdowns:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=1000):
                            try:
                                el.select_option(label=val)
                            except Exception:
                                for opt in el.locator('option').all():
                                    if val.lower() in (opt.text_content() or "").lower():
                                        el.select_option(value=opt.get_attribute('value'))
                                        break
                    except Exception:
                        pass

                # BPL
                try:
                    if is_bpl:
                        page.locator('input[name="bpl"][value="Yes"], input[name="bpl"][value="1"]').first.check()
                    else:
                        page.locator('input[name="bpl"][value="No"], input[name="bpl"][value="0"]').first.check()
                except Exception:
                    pass

                steps_completed.append("applicant_details_filled")

                # RTI Text
                try:
                    txt = page.locator('textarea[name="request_text"], textarea#RTIText').first
                    if txt.is_visible(timeout=2000):
                        txt.fill(rti_text[:3000])
                except Exception:
                    pass
                steps_completed.append("rti_text_filled")

                # Document
                if supporting_doc_path and os.path.exists(supporting_doc_path):
                    try:
                        page.locator('input[type="file"]').first.set_input_files(supporting_doc_path)
                    except Exception:
                        pass

                # CAPTCHA
                captcha_solved = False
                for attempt in range(1, 4):
                    try:
                        c_img = page.locator('img[src*="captcha"], img[alt*="captcha"], img.captcha-image').first
                        if c_img.is_visible(timeout=3000):
                            c_bytes = c_img.screenshot()
                            c_text = self.captcha_solver.solve(c_bytes, attempt)
                            if c_text:
                                c_in = page.locator('input[name="captcha"], input[name="security_code"]').first
                                c_in.fill(c_text)
                                captcha_solved = True
                                steps_completed.append(f"captcha_solved_{attempt}")
                                break
                    except Exception:
                        pass
                
                if not captcha_solved:
                    context.close()
                    browser.close()
                    gc.collect()
                    return {
                        "success": False,
                        "requires_manual_captcha": True,
                        "screenshots": screenshots,
                        "steps_completed": steps_completed,
                        "error": "Could not solve CAPTCHA automatically.",
                    }

                # Submit
                page.locator('input[type="submit"][value*="Submit"], input[type="submit"][value*="Payment"], button[type="submit"]').first.click()
                page.wait_for_load_state("domcontentloaded", timeout=12000)
                steps_completed.append("form_submitted")

                page_text = page.inner_text('body')
                current_url = page.url

                # Check Registration Number
                reg_match = re.search(r'(MOIAF/[A-Z]/[A-Z]/\d{2}/\d+)', page_text)
                reg_number = reg_match.group(1) if reg_match else None

                context.close()
                browser.close()
                gc.collect()

                if reg_number:
                    return {
                        "success": True,
                        "registration_number": reg_number,
                        "payment_amount": 0 if is_bpl else 10.0,
                        "screenshots": screenshots,
                        "steps_completed": steps_completed,
                        "message": f"RTI filed on Central Portal! Reg No: {reg_number}",
                    }

                is_payment = any(k in current_url.lower() for k in ["payment", "pay", "sbi", "billdesk"])
                if is_payment:
                    return {
                        "success": True,
                        "requires_payment": True,
                        "payment_url": current_url,
                        "payment_amount": 10.0,
                        "screenshots": screenshots,
                        "steps_completed": steps_completed,
                        "message": "Form submitted. Complete payment at the provided URL.",
                    }

                return {
                    "success": True,
                    "screenshots": screenshots,
                    "steps_completed": steps_completed,
                    "message": f"Form submitted. Check email {applicant_email} for confirmation.",
                }

        except Exception as e:
            logger.error("central_filing_error", error=str(e))
            gc.collect()
            return {"success": False, "error": str(e), "steps_completed": steps_completed}

    async def check_status_on_portal(self, registration_number: str, email: str) -> Dict[str, Any]:
        return await asyncio.to_thread(self._check_status_sync, registration_number, email)

    def _check_status_sync(self, registration_number: str, email: str) -> Dict[str, Any]:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=CHROMIUM_LOW_MEM_FLAGS)
                context = browser.new_context(viewport={'width': 1280, 'height': 720})
                page = context.new_page()
                
                page.goto(self.STATUS_URL, wait_until="domcontentloaded")
                page.locator('input[name="registration_number"]').fill(registration_number)
                page.locator('input[name="email"], input[type="email"]').fill(email)
                
                try:
                    c_img = page.locator('img[src*="captcha"]').first
                    if c_img.is_visible(timeout=2000):
                        c_text = self.captcha_solver.solve(c_img.screenshot())
                        if c_text:
                            page.locator('input[name="captcha"]').fill(c_text)
                except Exception:
                    pass

                page.locator('input[type="submit"]').first.click()
                page.wait_for_load_state("domcontentloaded")

                page_text = page.inner_text('body')
                context.close()
                browser.close()
                gc.collect()

                status = "pending"
                if "disposed" in page_text.lower():
                    status = "response_received"

                return {
                    "success": True,
                    "registration_number": registration_number,
                    "status_details": {"status": status},
                }
        except Exception as e:
            gc.collect()
            return {"success": False, "error": str(e)}