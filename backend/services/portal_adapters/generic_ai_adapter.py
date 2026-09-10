"""
AI-POWERED GENERIC PORTAL ADAPTER
Uses Google Gemini to analyze ANY government RTI portal's HTML
and automatically figure out how to fill the form.
"""

import json
import asyncio
import re
import base64
from typing import Dict, Optional, Any, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base_adapter import (
    BasePortalAdapter,
    FilingResult,
    StatusResult,
    ApplicantDetails,
    RTIRequestDetails,
    FilingStep,
)
from config.settings import settings
import structlog

logger = structlog.get_logger()


class GenericAIAdapter(BasePortalAdapter):
    """AI-powered adapter that can handle any RTI portal."""

    def __init__(self, portal_url: str = "", portal_name: str = "State RTI Portal"):
        super().__init__()
        self.portal_name = portal_name
        self.portal_url = portal_url
        self.submit_url = portal_url
        self.status_url = portal_url.replace("request", "status") if portal_url else ""
        self._form_schema: Optional[Dict[str, Any]] = None

    def supports_state(self, state: str) -> bool:
        return True

    def get_department_options(self, department_type: str, city: str = "") -> Dict[str, str]:
        return {
            "department": department_type.replace("_", " ").title(),
            "authority": department_type.replace("_", " ").title(),
        }

    async def analyze_portal_form(self, page: Page) -> Dict[str, Any]:
        """Use Google Gemini AI to analyze the portal's form structure."""
        if self._form_schema:
            return self._form_schema

        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-1.5-flash")

            html = await page.content()
            form_match = re.search(r"<form[^>]*>.*?</form>", html, re.DOTALL | re.IGNORECASE)
            form_html = form_match.group(0) if form_match else html[:15000]

            if len(form_html) > 20000:
                form_html = form_html[:20000] + "\n... (truncated)"

            prompt = (
                "You are an expert web form analyzer specializing in Indian government portals.\n\n"
                "Analyze this HTML form from an Indian government RTI portal and identify ALL form fields.\n\n"
                "HTML:\n"
                + form_html
                + "\n\n"
                "Return a JSON object with this EXACT structure (no markdown, no code blocks, just raw JSON):\n"
                "{\n"
                '    "department_select": "CSS selector for department/ministry dropdown",\n'
                '    "authority_select": "CSS selector for public authority dropdown",\n'
                '    "name_input": "CSS selector for applicant name text field",\n'
                '    "gender_select": "CSS selector for gender dropdown",\n'
                '    "address_input": "CSS selector for address textarea or input",\n'
                '    "pincode_input": "CSS selector for pincode text field",\n'
                '    "state_select": "CSS selector for state dropdown",\n'
                '    "district_select": "CSS selector for district dropdown (null if not present)",\n'
                '    "phone_input": "CSS selector for phone/mobile number field",\n'
                '    "email_input": "CSS selector for email field",\n'
                '    "bpl_radio_yes": "CSS selector for BPL Yes radio button",\n'
                '    "bpl_radio_no": "CSS selector for BPL No radio button",\n'
                '    "life_liberty_yes": "CSS selector for Life/Liberty Yes radio",\n'
                '    "life_liberty_no": "CSS selector for Life/Liberty No radio",\n'
                '    "rti_textarea": "CSS selector for RTI application text area",\n'
                '    "file_upload": "CSS selector for file upload input",\n'
                '    "captcha_image": "CSS selector for CAPTCHA image",\n'
                '    "captcha_input": "CSS selector for CAPTCHA text input",\n'
                '    "captcha_refresh": "CSS selector for CAPTCHA refresh button/link",\n'
                '    "submit_button": "CSS selector for submit/make payment button",\n'
                '    "education_select": "CSS selector for education dropdown",\n'
                '    "urban_rural_select": "CSS selector for urban/rural status dropdown",\n'
                '    "citizenship_select": "CSS selector for citizenship dropdown",\n'
                '    "form_action_url": "URL the form submits to (from action attribute)",\n'
                '    "form_method": "GET or POST",\n'
                '    "has_aspnet_viewstate": true or false,\n'
                '    "requires_javascript_submit": true or false,\n'
                '    "notes": "Any special observations about this form"\n'
                "}\n\n"
                "IMPORTANT RULES:\n"
                "1. Use CSS selectors that work with Playwright browser automation\n"
                "2. Prefer ID selectors like #txtName over class selectors\n"
                "3. For ASP.NET forms use attribute selectors like [id$='txtName'] or [name$='txtName']\n"
                "4. If a field does not exist on this form, use null\n"
                "5. Be specific and accurate - wrong selectors will cause filing to fail\n"
                "6. For radio buttons, provide separate selectors for Yes and No options\n"
                "7. Include the CAPTCHA refresh button selector if one exists"
            )

            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 2048},
            )

            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            if text.startswith("json"):
                text = text[4:]

            self._form_schema = json.loads(text.strip())

            fields_found = sum(
                1 for v in self._form_schema.values()
                if v is not None and v != "null"
            )

            logger.info(
                "portal_form_analyzed_by_ai",
                portal=self.portal_url,
                fields_found=fields_found,
                total_fields=len(self._form_schema),
            )

            return self._form_schema

        except json.JSONDecodeError as e:
            logger.error("ai_response_not_valid_json", error=str(e))
            return self._get_fallback_schema()

        except Exception as e:
            logger.error("ai_form_analysis_failed", error=str(e))
            return self._get_fallback_schema()

    def _get_fallback_schema(self) -> Dict[str, Any]:
        """Generic fallback selectors that work on most Indian RTI portals."""
        return {
            "department_select": "select[name*='department'], select[name*='ministry'], select[id*='dept'], select[id*='Dept'], select[id*='ddlDept']",
            "authority_select": "select[name*='authority'], select[name*='public'], select[id*='auth'], select[id*='Auth'], select[id*='ddlAuth']",
            "name_input": "input[name*='name'][type='text'], input[id*='Name'][type='text'], input[id*='txtName'], input[name*='applicant']",
            "gender_select": "select[name*='gender'], select[id*='gender'], select[id*='Gender'], select[id*='ddlGender']",
            "address_input": "textarea[name*='address'], textarea[id*='Address'], textarea[id*='txtAddress'], input[name*='address']",
            "pincode_input": "input[name*='pincode'], input[name*='pin'], input[id*='Pincode'], input[id*='txtPin']",
            "state_select": "select[name*='state'], select[id*='state'], select[id*='State'], select[id*='ddlState']",
            "district_select": "select[name*='district'], select[id*='district'], select[id*='District'], select[id*='ddlDistrict']",
            "phone_input": "input[name*='phone'], input[name*='mobile'], input[name*='tel'], input[id*='Phone'], input[id*='Mobile'], input[id*='txtPhone']",
            "email_input": "input[name*='email'], input[type='email'], input[id*='Email'], input[id*='txtEmail']",
            "bpl_radio_yes": "input[name*='bpl'][value='Yes'], input[name*='bpl'][value='1'], input[id*='BPL'][value='Yes'], input[id*='rdoBPLYes']",
            "bpl_radio_no": "input[name*='bpl'][value='No'], input[name*='bpl'][value='0'], input[id*='BPL'][value='No'], input[id*='rdoBPLNo']",
            "life_liberty_yes": "input[name*='life'][value='Yes'], input[name*='life'][value='1'], input[id*='rdoLifeYes']",
            "life_liberty_no": "input[name*='life'][value='No'], input[name*='life'][value='0'], input[id*='rdoLifeNo']",
            "rti_textarea": "textarea[name*='text'], textarea[name*='request'], textarea[name*='rti'], textarea[id*='RTI'], textarea[id*='txtRTI'], textarea[id*='txtRequest'], textarea[name*='application']",
            "file_upload": "input[type='file']",
            "captcha_image": "img[src*='captcha'], img[alt*='captcha'], img[alt*='Captcha'], img[alt*='CAPTCHA'], img[id*='captcha'], img[id*='Captcha'], img[id*='imgCaptcha']",
            "captcha_input": "input[name*='captcha'], input[name*='security'], input[id*='captcha'], input[id*='Captcha'], input[id*='txtCaptcha'], input[id*='txtSecurity']",
            "captcha_refresh": "a[onclick*='captcha'], a[href*='captcha'], img[onclick*='captcha'], button[onclick*='captcha'], a[id*='lnkRefresh'], a[id*='refresh']",
            "submit_button": "input[type='submit'], button[type='submit'], input[id*='btnSubmit'], input[id*='Submit'], input[value*='Submit'], input[value*='Payment']",
            "education_select": "select[name*='education'], select[name*='edu'], select[id*='Education'], select[id*='ddlEducation']",
            "urban_rural_select": "select[name*='urban'], select[name*='status'], select[id*='Status'], select[id*='ddlStatus']",
            "citizenship_select": "select[name*='country'], select[name*='citizen'], select[id*='Country'], select[id*='ddlCountry']",
            "form_action_url": "",
            "form_method": "POST",
            "has_aspnet_viewstate": False,
            "requires_javascript_submit": False,
            "notes": "Fallback schema - generic selectors for most portals",
        }

    async def file_rti(self, applicant: ApplicantDetails, rti_request: RTIRequestDetails, page: Page = None) -> FilingResult:
        """File RTI on any portal using AI-analyzed form structure."""
        from services.rti_filing_service import CaptchaSolver

        screenshots: List[str] = []
        steps: List[str] = []
        captcha_solver = CaptchaSolver()
        owns_page = page is None

        try:
            if owns_page:
                from services.rti_filing_service import RTIFilingService
                filing_svc = RTIFilingService()
                context = await filing_svc._create_context()
                page = await context.new_page()
                page.set_default_timeout(30000)
                page.set_default_navigation_timeout(60000)

            logger.info("generic_ai_navigate", portal=self.portal_url)
            submit_url = self.submit_url or self.portal_url
            await page.goto(submit_url, wait_until="networkidle")
            steps.append(FilingStep.NAVIGATE.value)
            screenshots.append(base64.b64encode(await page.screenshot()).decode())

            try:
                checkbox = page.locator("input[type='checkbox']").first
                await checkbox.wait_for(state="visible", timeout=3000)
                await checkbox.check()
                proceed_btn = page.locator("input[type='submit'], button[type='submit']").first
                await proceed_btn.click()
                await page.wait_for_load_state("networkidle")
                steps.append(FilingStep.GUIDELINES.value)
            except PlaywrightTimeout:
                steps.append("guidelines_skipped")

            logger.info("generic_ai_analyzing_form")
            schema = await self.analyze_portal_form(page)
            steps.append("ai_form_analysis_complete")

            dept_selector = schema.get("department_select")
            if dept_selector:
                dept_options = self.get_department_options(rti_request.department_type, applicant.city)
                await self._safe_select(
                    page,
                    dept_selector,
                    dept_options.get("department", rti_request.department_type.replace("_", " ").title()),
                )
                await asyncio.sleep(2)
                steps.append(FilingStep.SELECT_DEPT.value)

                auth_selector = schema.get("authority_select")
                if auth_selector:
                    await self._safe_select(
                        page,
                        auth_selector,
                        dept_options.get("authority", rti_request.department_type.replace("_", " ").title()),
                    )
                    await asyncio.sleep(1)
                    steps.append(FilingStep.SELECT_AUTHORITY.value)

            if applicant.is_life_liberty:
                ll_yes = schema.get("life_liberty_yes")
                if ll_yes:
                    await self._safe_click(page, ll_yes)
            else:
                ll_no = schema.get("life_liberty_no")
                if ll_no:
                    await self._safe_click(page, ll_no)
            steps.append(FilingStep.LIFE_LIBERTY.value)

            text_fields = {
                "name_input": applicant.name,
                "address_input": applicant.address,
                "pincode_input": applicant.pincode,
                "phone_input": applicant.phone,
                "email_input": applicant.email,
            }

            for field_key, value in text_fields.items():
                selector = schema.get(field_key)
                if selector and value:
                    await self._safe_fill(page, selector, value)
                    steps.append("filled_" + field_key)

            dropdown_fields = {
                "gender_select": applicant.gender.title(),
                "state_select": applicant.state.title(),
                "education_select": "Graduate & Above",
                "urban_rural_select": applicant.area_type.title(),
                "citizenship_select": "Indian",
            }

            for field_key, value in dropdown_fields.items():
                selector = schema.get(field_key)
                if selector:
                    await self._safe_select(page, selector, value)
                    steps.append("selected_" + field_key)

            district_selector = schema.get("district_select")
            if district_selector and applicant.district:
                await self._safe_select(page, district_selector, applicant.district.title())

            if applicant.is_bpl:
                bpl_yes = schema.get("bpl_radio_yes")
                if bpl_yes:
                    await self._safe_click(page, bpl_yes)
            else:
                bpl_no = schema.get("bpl_radio_no")
                if bpl_no:
                    await self._safe_click(page, bpl_no)
            steps.append(FilingStep.FILL_BPL.value)

            screenshots.append(base64.b64encode(await page.screenshot()).decode())

            rti_selector = schema.get("rti_textarea")
            if rti_selector:
                rti_text = rti_request.rti_text[:self.max_text_length]
                await self._safe_fill(page, rti_selector, rti_text)
                steps.append(FilingStep.FILL_TEXT.value)
            else:
                logger.warning("generic_ai_rti_textarea_not_found")

            file_selector = schema.get("file_upload")
            if file_selector and rti_request.supporting_doc_path:
                try:
                    file_input = page.locator(file_selector).first
                    await file_input.set_input_files(rti_request.supporting_doc_path)
                    steps.append(FilingStep.UPLOAD_DOC.value)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning("generic_ai_file_upload_failed", error=str(e))

            captcha_img_sel = schema.get("captcha_image")
            captcha_input_sel = schema.get("captcha_input")
            captcha_refresh_sel = schema.get("captcha_refresh")

            captcha_solved = False

            if captcha_img_sel and captcha_input_sel:
                for attempt in range(1, 6):
                    try:
                        captcha_img = page.locator(captcha_img_sel).first
                        await captcha_img.wait_for(state="visible", timeout=5000)
                        captcha_bytes = await captcha_img.screenshot()
                        captcha_text = await captcha_solver.solve(captcha_bytes, attempt)

                        if captcha_text:
                            await self._safe_fill(page, captcha_input_sel, captcha_text)
                            captcha_solved = True
                            steps.append(FilingStep.SOLVE_CAPTCHA.value + "_" + str(attempt))
                            break
                        else:
                            if captcha_refresh_sel:
                                try:
                                    refresh_btn = page.locator(captcha_refresh_sel).first
                                    await refresh_btn.click()
                                    await asyncio.sleep(1)
                                except Exception:
                                    pass
                    except PlaywrightTimeout:
                        logger.warning("generic_ai_captcha_not_found", attempt=attempt)
                        break
                    except Exception as e:
                        logger.error("generic_ai_captcha_error", attempt=attempt, error=str(e))

            if not captcha_solved and captcha_img_sel:
                captcha_b64 = None
                try:
                    captcha_bytes = await page.locator(captcha_img_sel).first.screenshot()
                    captcha_b64 = base64.b64encode(captcha_bytes).decode()
                except Exception:
                    pass

                screenshots.append(base64.b64encode(await page.screenshot()).decode())

                return FilingResult(
                    success=False,
                    requires_manual_captcha=True,
                    captcha_image_base64=captcha_b64,
                    screenshots=screenshots,
                    steps_completed=steps,
                    error="Could not solve CAPTCHA automatically. Please try again or solve manually.",
                    portal_name=self.portal_name,
                    portal_url=self.portal_url,
                )

            screenshots.append(base64.b64encode(await page.screenshot()).decode())

            logger.info("generic_ai_submitting_form")
            submit_sel = schema.get("submit_button")

            if submit_sel:
                submit_btn = page.locator(submit_sel).first
                await submit_btn.click()

                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except PlaywrightTimeout:
                    pass

                await asyncio.sleep(3)
                steps.append(FilingStep.SUBMIT.value)
            else:
                logger.error("generic_ai_submit_button_not_found")
                return FilingResult(
                    success=False,
                    screenshots=screenshots,
                    steps_completed=steps,
                    error="Could not find submit button on the portal.",
                    portal_name=self.portal_name,
                )

            screenshots.append(base64.b64encode(await page.screenshot()).decode())

            current_url = page.url
            page_text = await page.inner_text("body")

            if ("captcha" in page_text.lower() and
                ("incorrect" in page_text.lower() or "wrong" in page_text.lower() or "invalid" in page_text.lower())):
                return FilingResult(
                    success=False,
                    requires_manual_captcha=True,
                    screenshots=screenshots,
                    steps_completed=steps,
                    error="CAPTCHA was incorrect. Please try again.",
                    portal_name=self.portal_name,
                )

            payment_keywords = ["payment", "pay", "sbi", "treasury", "epay", "razorpay", "billdesk", "payu"]
            is_payment_page = any(kw in current_url.lower() for kw in payment_keywords)

            if is_payment_page or "payment" in page_text.lower()[:500]:
                steps.append(FilingStep.PAYMENT.value)
                return FilingResult(
                    success=True,
                    requires_payment=True,
                    payment_url=current_url,
                    payment_amount=0 if applicant.is_bpl else 10.0,
                    screenshots=screenshots,
                    steps_completed=steps,
                    message="Form submitted on " + self.portal_name + ". Please complete payment of Rs. 10.",
                    portal_name=self.portal_name,
                    portal_url=self.portal_url,
                )

            reg_number = self._extract_registration_number(page_text)

            if reg_number:
                steps.append(FilingStep.CAPTURE_REG.value)
                return FilingResult(
                    success=True,
                    registration_number=reg_number,
                    payment_amount=0 if applicant.is_bpl else 10.0,
                    screenshots=screenshots,
                    steps_completed=steps,
                    message="RTI filed on " + self.portal_name + "! Registration Number: " + reg_number,
                    portal_name=self.portal_name,
                    portal_url=self.portal_url,
                )

            return FilingResult(
                success=True,
                screenshots=screenshots,
                steps_completed=steps,
                message=(
                    "Form appears to have been submitted on " + self.portal_name +
                    ". Please check your email (" + applicant.email +
                    ") for the Registration Number and payment link."
                ),
                portal_name=self.portal_name,
                portal_url=self.portal_url,
                raw_page_text=page_text[:2000],
            )

        except PlaywrightTimeout as e:
            logger.error("generic_ai_portal_timeout", error=str(e))
            return FilingResult(
                success=False,
                screenshots=screenshots,
                steps_completed=steps,
                error="Portal took too long to respond. The government website may be slow or down. Please try again later.",
                portal_name=self.portal_name,
            )

        except Exception as e:
            logger.error("generic_ai_filing_failed", error=str(e))
            return FilingResult(
                success=False,
                screenshots=screenshots,
                steps_completed=steps,
                error="AI adapter error: " + str(e),
                portal_name=self.portal_name,
            )

        finally:
            if owns_page and page:
                try:
                    await page.context.close()
                except Exception:
                    pass

    async def check_status(self, registration_number: str, email: str, page: Page = None) -> StatusResult:
        """Check RTI status on the portal using AI-analyzed form."""
        from services.rti_filing_service import CaptchaSolver

        captcha_solver = CaptchaSolver()
        owns_page = page is None

        try:
            if owns_page:
                from services.rti_filing_service import RTIFilingService
                filing_svc = RTIFilingService()
                context = await filing_svc._create_context()
                page = await context.new_page()
                page.set_default_timeout(30000)

            status_url = self.status_url or self.portal_url
            await page.goto(status_url, wait_until="networkidle")

            html = await page.content()
            form_match = re.search(r"<form[^>]*>.*?</form>", html, re.DOTALL | re.IGNORECASE)
            form_html = form_match.group(0) if form_match else html[:10000]

            if len(form_html) > 15000:
                form_html = form_html[:15000]

            import google.generativeai as genai
            genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-1.5-flash")

            prompt = (
                "Analyze this HTML form from an Indian RTI status check page.\n\n"
                "HTML:\n" + form_html + "\n\n"
                "Return JSON:\n"
                "{\n"
                '    "reg_number_input": "CSS selector for registration number field",\n'
                '    "email_input": "CSS selector for email field",\n'
                '    "captcha_image": "CSS selector for CAPTCHA image",\n'
                '    "captcha_input": "CSS selector for CAPTCHA input",\n'
                '    "submit_button": "CSS selector for submit/search button"\n'
                "}"
            )

            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 512},
            )

            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            if text.startswith("json"):
                text = text[4:]

            status_schema = json.loads(text.strip())

            reg_sel = status_schema.get("reg_number_input")
            if reg_sel:
                await self._safe_fill(page, reg_sel, registration_number)

            email_sel = status_schema.get("email_input")
            if email_sel:
                await self._safe_fill(page, email_sel, email)

            captcha_img_sel = status_schema.get("captcha_image")
            captcha_input_sel = status_schema.get("captcha_input")

            if captcha_img_sel and captcha_input_sel:
                for attempt in range(1, 4):
                    try:
                        captcha_img = page.locator(captcha_img_sel).first
                        await captcha_img.wait_for(state="visible", timeout=5000)
                        captcha_bytes = await captcha_img.screenshot()
                        captcha_text = await captcha_solver.solve(captcha_bytes, attempt)
                        if captcha_text:
                            await self._safe_fill(page, captcha_input_sel, captcha_text)
                            break
                    except Exception:
                        pass

            submit_sel = status_schema.get("submit_button")
            if submit_sel:
                await page.locator(submit_sel).first.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)

            page_text = await page.inner_text("body")
            screenshot = base64.b64encode(await page.screenshot()).decode()

            status = "unknown"
            text_lower = page_text.lower()

            if "disposed" in text_lower or "replied" in text_lower:
                status = "response_received"
            elif "pending" in text_lower:
                status = "pending"
            elif "transferred" in text_lower:
                status = "transferred"
            elif "rejected" in text_lower or "denied" in text_lower:
                status = "rejected"

            return StatusResult(
                success=True,
                registration_number=registration_number,
                status=status,
                raw_text=page_text[:3000],
                screenshot=screenshot,
            )

        except Exception as e:
            logger.error("generic_ai_status_check_failed", error=str(e))
            return StatusResult(
                success=False,
                error="AI status check failed: " + str(e),
            )

        finally:
            if owns_page and page:
                try:
                    await page.context.close()
                except Exception:
                    pass

    def _extract_registration_number(self, page_text: str) -> Optional[str]:
        """Try to extract registration number from the confirmation page."""
        patterns = [
            r"MOIAF/[A-Z]/[A-Z]/\d{2}/\d+",
            r"[A-Z]{2,5}/[A-Z]+/\d{4}/\d+",
            r"[A-Z]{2,5}/[A-Z]/[A-Z]/\d{2}/\d+",
            r"Registration\s*(?:No|Number|ID)[:\s]*([A-Z0-9/\-]+)",
            r"Reg\.\s*(?:No|Number)[:\s]*([A-Z0-9/\-]+)",
            r"Reference\s*(?:No|Number)[:\s]*([A-Z0-9/\-]+)",
            r"Application\s*(?:No|Number)[:\s]*([A-Z0-9/\-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                result = match.group(1) if match.groups() else match.group(0)
                result = result.strip().rstrip(".")
                if len(result) >= 5:
                    return result

        return None

    async def _safe_fill(self, page: Page, selector: str, value: str) -> bool:
        """Safely fill a form field."""
        selectors = [s.strip() for s in selector.split(",")]

        for sel in selectors:
            if not sel:
                continue
            try:
                element = page.locator(sel).first
                await element.wait_for(state="visible", timeout=2000)
                await element.click()
                await element.fill("")
                await element.type(value, delay=15)
                return True
            except Exception:
                continue

        logger.debug("generic_ai_field_not_found", selector=selector[:60])
        return False

    async def _safe_select(self, page: Page, selector: str, value: str) -> bool:
        """Safely select a dropdown option."""
        selectors = [s.strip() for s in selector.split(",")]

        for sel in selectors:
            if not sel:
                continue
            try:
                element = page.locator(sel).first
                await element.wait_for(state="visible", timeout=2000)

                try:
                    await element.select_option(label=value)
                    return True
                except Exception:
                    pass

                options = await element.locator("option").all()
                for option in options:
                    text = await option.text_content()
                    if text and value.lower() in text.lower():
                        opt_value = await option.get_attribute("value")
                        if opt_value and opt_value != "":
                            await element.select_option(value=opt_value)
                            return True

            except Exception:
                continue

        logger.debug("generic_ai_select_not_found", selector=selector[:60], value=value)
        return False

    async def _safe_click(self, page: Page, selector: str) -> bool:
        """Safely click an element (radio button, checkbox, etc.)."""
        selectors = [s.strip() for s in selector.split(",")]

        for sel in selectors:
            if not sel:
                continue
            try:
                element = page.locator(sel).first
                await element.wait_for(state="visible", timeout=2000)
                await element.check()
                return True
            except Exception:
                try:
                    element = page.locator(sel).first
                    await element.click()
                    return True
                except Exception:
                    continue

        return False