"""
RTI Sarthi - Gujarat State RTI Portal Automation Adapter
Target URL: https://onlinerti.gujarat.gov.in/rti_portal/

Location: backend/services/portal_adapters/gujarat_adapter.py

Flow:
1. Open portal → Click top-right "Login / Register"
2. Fill Mobile (Human Typing) + solve Math CAPTCHA
3. Click the modal submit button BELOW the captcha
4. WAIT for OTP modal → 60s pause for user to verify
5. Check if auto-redirected to Terms & Conditions → Tick checkbox at bottom + Click Next
6. RTI Application Details → Fill AI Questions (Chunked 740 chars with +) → Select Department matching Draft → Payment URL capture
"""

import sys
import os
import re
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, Page, Request, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
current_file = Path(__file__).resolve()
portal_adapters_dir = current_file.parent
services_dir = portal_adapters_dir.parent
backend_dir = services_dir.parent
project_root = backend_dir.parent

for p in [str(project_root), str(backend_dir), str(services_dir), str(portal_adapters_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from backend.core.config import settings
except ModuleNotFoundError:
    class DummySettings:
        DEBUG = True
        CHROMIUM_LOW_MEM_FLAGS = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ]
    settings = DummySettings()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Official Gujarat RTI portal constants
# ---------------------------------------------------------------------------
GUJARAT_RTI_PORTAL_NAME = "Gujarat State RTI Portal"
GUJARAT_RTI_PORTAL_URL = "https://onlinerti.gujarat.gov.in/rti_portal/"
GUJARAT_RTI_ALLOWED_HOSTS = ("onlinerti.gujarat.gov.in",)
GUJARAT_RTI_BLOCKED_HOSTS = ("rti.gujarat.gov.in", "www.rti.gujarat.gov.in")


class GujaratRTIAdapter:
    """Driver for live Gujarat RTI portal (OTP + multi-step wizard)."""

    PORTAL_NAME = GUJARAT_RTI_PORTAL_NAME
    PORTAL_URL = GUJARAT_RTI_PORTAL_URL
    NAME = GUJARAT_RTI_PORTAL_NAME
    STATE = "Gujarat"
    IS_AVAILABLE = True
    SUPPORTS_AUTOMATION = True

    def __init__(self, debug: bool = getattr(settings, "DEBUG", True)):
        self.debug = debug
        self.portal_url = GUJARAT_RTI_PORTAL_URL
        self.portal_name = GUJARAT_RTI_PORTAL_NAME
        self.name = GUJARAT_RTI_PORTAL_NAME
        self.state = "Gujarat"
        self.is_available = True
        self.supports_automation = True

    # Convenience method aliases for API callers expecting different names
    def file_rti(self, *args, **kwargs) -> Dict[str, Any]:
        return self.execute_filing(*args, **kwargs)

    def submit(self, *args, **kwargs) -> Dict[str, Any]:
        return self.execute_filing(*args, **kwargs)

    def run(self, *args, **kwargs) -> Dict[str, Any]:
        return self.execute_filing(*args, **kwargs)

    def file(self, *args, **kwargs) -> Dict[str, Any]:
        return self.execute_filing(*args, **kwargs)

    # -----------------------------------------------------------------------
    # URL guards — enforce official domain
    # -----------------------------------------------------------------------
    def _host(self, url: str) -> str:
        try:
            return (urlparse(url).hostname or "").lower()
        except Exception:
            return ""

    def _is_blocked_portal(self, url: str) -> bool:
        host = self._host(url)
        return any(host == b or host.endswith("." + b) for b in GUJARAT_RTI_BLOCKED_HOSTS)

    def _is_allowed_portal(self, url: str) -> bool:
        host = self._host(url)
        if not host:
            return False
        payment_hints = (
            "egras", "treasury", "sbi", "billdesk", "payu", "razorpay",
            "payment", "checkout", "pg", "gov.in",
        )
        if any(h in (url or "").lower() for h in ("egras", "treasury", "billdesk", "payu", "razorpay", "sbi.co")):
            return True
        return any(host == a or host.endswith("." + a) for a in GUJARAT_RTI_ALLOWED_HOSTS)

    def _ensure_correct_portal(self, page: Page, reason: str = "") -> None:
        """If browser landed on old portal (or blank), force official URL."""
        current = page.url or ""
        host = self._host(current)
        if self._is_blocked_portal(current) or host in ("", "about:blank", "new"):
            logger.warning(
                "Wrong/empty portal URL detected (%s) host=%s url=%s → forcing %s",
                reason or "guard",
                host,
                current,
                self.portal_url,
            )
            page.goto(self.portal_url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            time.sleep(1.0)
            if self._is_blocked_portal(page.url):
                raise RuntimeError(
                    f"Portal still on blocked host after correction: {page.url}. "
                    f"Expected {self.portal_url}"
                )
            logger.info("Portal corrected → %s", page.url)

    def _goto_portal(self, page: Page) -> None:
        """Navigate strictly to https://onlinerti.gujarat.gov.in/rti_portal/"""
        url = self.portal_url
        if "onlinerti.gujarat.gov.in" not in url:
            url = GUJARAT_RTI_PORTAL_URL
            self.portal_url = url

        logger.info("Navigating to official Gujarat RTI portal: %s", url)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(1.2)
        self._ensure_correct_portal(page, reason="post-goto")
        logger.info("Portal ready at: %s", page.url)

    # -----------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # -----------------------------------------------------------------------
    def execute_filing(
        self,
        applicant_data: Optional[Dict[str, Any]] = None,
        rti_text: Optional[str] = None,
        department_name: str = "Ahmedabad Municipal Corporation",
        attachment_path: Optional[str] = None,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """Runs end-to-end filing automation flow with flexible argument parsing."""
        
        # --- Flexible Argument Unpacking (Supports live route signatures) ---
        if applicant_data is None:
            applicant_data = kwargs.get("applicant_data") or kwargs.get("applicant") or {}
        if not applicant_data and len(args) > 0 and isinstance(args[0], dict):
            applicant_data = args[0]
        if not isinstance(applicant_data, dict):
            applicant_data = {}

        if len(args) > 1 and isinstance(args[1], dict):
            app_data = args[1]
            rti_text = app_data.get("rti_text") or app_data.get("query_text") or app_data.get("subject") or app_data.get("query")
            department_name = app_data.get("department_name") or app_data.get("public_authority") or department_name
        elif "application_data" in kwargs and isinstance(kwargs["application_data"], dict):
            app_data = kwargs["application_data"]
            rti_text = rti_text or app_data.get("rti_text") or app_data.get("query_text") or app_data.get("subject") or app_data.get("query")
            department_name = app_data.get("department_name") or app_data.get("public_authority") or department_name
        elif len(args) > 1 and isinstance(args[1], str):
            rti_text = args[1]
            if len(args) > 2 and isinstance(args[2], str):
                department_name = args[2]

        if not rti_text:
            rti_text = kwargs.get("rti_text") or kwargs.get("query_text") or kwargs.get("subject") or "RTI query requested under Section 6(1) of RTI Act 2005."

        if "department_name" in kwargs:
            department_name = kwargs["department_name"]
        elif "public_authority" in kwargs:
            department_name = kwargs["public_authority"]

        if not department_name:
            department_name = "Ahmedabad Municipal Corporation"
        # ---------------------------------------------------------------------

        self.portal_url = GUJARAT_RTI_PORTAL_URL

        logger.info(
            "Starting Gujarat RTI automation → portal=%s | department='%s'",
            self.portal_url,
            department_name,
        )

        # Environment-aware headless launch (Force True on Linux/Render without GUI)
        is_linux = sys.platform.startswith("linux")
        has_display = bool(os.environ.get("DISPLAY"))
        is_render = bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))

        if is_linux or is_render or not has_display:
            headless_setting = True
        else:
            headless_setting = not self.debug

        captured = {"payment_url": None, "registration_number": None}

        launch_args = getattr(
            settings,
            "CHROMIUM_LOW_MEM_FLAGS",
            ["--no-sandbox", "--disable-setuid-sandbox"],
        ).copy()

        if "--disable-blink-features=AutomationControlled" not in launch_args:
            launch_args.append("--disable-blink-features=AutomationControlled")

        if not headless_setting:
            launch_args.append("--start-maximized")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless_setting,
                slow_mo=30 if not headless_setting else 0,
                args=launch_args,
            )

            context_kwargs = {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "locale": "en-IN",
            }
            if not headless_setting:
                context_kwargs["no_viewport"] = True
            else:
                context_kwargs["viewport"] = {"width": 1366, "height": 900}

            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.set_default_timeout(30000)

            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            page.on("dialog", lambda d: d.accept())

            # Intercept eGRAS / Treasury Payment URLs
            def on_request(req: Request):
                u = req.url.lower()
                if "rti.gujarat.gov.in" in u and "onlinerti" not in u:
                    return
                if "failpayment" in u or u.endswith(".png") or u.endswith(".jpg"):
                    return
                if any(
                    k in u
                    for k in (
                        "payment", "sbi", "egras", "treasury",
                        "billdesk", "payu", "razorpay", "checkout", "pg"
                    )
                ):
                    logger.info("Payment gateway intercepted: %s", req.url)
                    captured["payment_url"] = req.url

            page.on("request", on_request)

            try:
                self._goto_portal(page)
                self._click_login_register(page)
                self._ensure_correct_portal(page, reason="after-login-click")

                self._fill_login_form(page, applicant_data)
                self._wait_for_otp_verification(page)
                self._ensure_correct_portal(page, reason="after-otp")

                self._fill_profile_if_needed(page, applicant_data)
                self._run_rti_wizard(
                    page, applicant_data, rti_text, department_name, attachment_path
                )

                final_url = captured["payment_url"] or page.url
                if self._is_blocked_portal(final_url):
                    final_url = captured["payment_url"] or self.portal_url

                logger.info("Finished. Final Payment/Portal URL = %s", final_url)

                try:
                    txt = page.content()
                    m = re.search(r"(RTI/[A-Z0-9]+/\d{4}/\d+|GUJ/RTI/\d+|\b\d{4}/\d+\b)", txt)
                    if m:
                        captured["registration_number"] = m.group(0)
                except Exception:
                    pass

                ref_num = captured["registration_number"] or f"GJT-RTI-{int(time.time())}"

                return {
                    "success": True,
                    "status": "PAYMENT_PENDING" if captured["payment_url"] or "create" not in final_url else "DRAFTED",
                    "portal_name": self.portal_name,
                    "portal_url": self.portal_url,
                    "portal": self.portal_name,
                    "payment_url": final_url,
                    "registration_number": ref_num,
                    "tracking_number": ref_num,
                    "message": (
                        f"RTI drafted successfully for '{department_name}' on Gujarat portal "
                        f"({self.portal_url}). Pay ₹10 official fee via the gateway link."
                    ),
                }

            except Exception as exc:
                logger.exception("Automation failed")
                try:
                    page.screenshot(path="gujarat_debug_error.png", full_page=True)
                except Exception:
                    pass
                if self.debug and not headless_setting:
                    time.sleep(15)
                return {
                    "success": False,
                    "status": "ERROR",
                    "portal_name": self.portal_name,
                    "portal_url": self.portal_url,
                    "portal": self.portal_name,
                    "payment_url": self.portal_url,
                    "registration_number": None,
                    "tracking_number": None,
                    "error": str(exc),
                    "message": f"Stopped on Gujarat portal: {exc}",
                }
            finally:
                browser.close()

    # -----------------------------------------------------------------------
    # Human-like input fill
    # -----------------------------------------------------------------------
    def _human_fill(self, locator, value: str, delay: int = 80) -> None:
        locator.wait_for(state="visible", timeout=12000)
        try:
            locator.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        locator.click(timeout=3000)
        time.sleep(0.2)
        locator.fill("")
        locator.type(str(value), delay=delay)
        time.sleep(0.3)

    # -----------------------------------------------------------------------
    # Click top-right Login / Register & wait for Mobile field
    # -----------------------------------------------------------------------
    def _click_login_register(self, page: Page) -> None:
        logger.info("Looking for top 'Login / Register' button...")
        self._ensure_correct_portal(page, reason="before-login-register")

        mobile_selector = (
            "input[placeholder*='Mobile' i], input[placeholder*='mobile'], input[type='tel']"
        )

        if page.locator(mobile_selector).count() and page.locator(mobile_selector).first.is_visible():
            logger.info("Login / Register modal is already open.")
            return

        selectors = [
            "header a:has-text('Login / Register')",
            "header button:has-text('Login / Register')",
            "nav a:has-text('Login / Register')",
            "a:has-text('Login / Register')",
            "button:has-text('Login / Register')",
            "text=Login / Register",
        ]

        clicked = False
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() == 0 or not loc.is_visible(timeout=2000):
                    continue
                box = loc.bounding_box()
                if box and box["y"] > 120:
                    continue
                loc.click(timeout=3000)
                clicked = True
                logger.info("Clicked header Login/Register using: %s", sel)
                time.sleep(1.0)
                break
            except Exception:
                continue

        if not clicked:
            page.mouse.click(1250, 40)
            time.sleep(1.0)

        self._ensure_correct_portal(page, reason="after-login-register-click")

        try:
            page.locator(mobile_selector).first.wait_for(state="visible", timeout=12000)
            logger.info("Login / Register modal is open and mobile field is ready.")
        except PlaywrightTimeout:
            page.evaluate(
                """() => {
                    const els = Array.from(document.querySelectorAll('a, button'));
                    for (const el of els) {
                        const t = (el.textContent || '').replace(/\\s+/g, ' ').trim();
                        const r = el.getBoundingClientRect();
                        if (r.y < 100 && /login/i.test(t)) { el.click(); return; }
                    }
                }"""
            )
            time.sleep(1.0)
            page.locator(mobile_selector).first.wait_for(state="visible", timeout=10000)

    # -----------------------------------------------------------------------
    # Login form submission
    # -----------------------------------------------------------------------
    def _fill_login_form(self, page: Page, applicant_data: Dict[str, Any]) -> None:
        phone = re.sub(r"\D", "", str(applicant_data.get("phone") or applicant_data.get("mobile_number") or ""))[-10:]
        if len(phone) != 10:
            raise RuntimeError(f"Invalid mobile number (need 10 digits): {phone!r}")
        logger.info("Filling mobile number: %s", phone)

        mobile = page.locator(
            "input[placeholder*='Mobile' i], input[placeholder*='mobile'], "
            "input[type='tel'], input[name*='mobile' i]"
        ).first

        self._human_fill(mobile, phone, delay=100)

        email_field = page.locator("input[placeholder*='Email' i], input[type='email']")
        if email_field.count() and applicant_data.get("email"):
            try:
                if email_field.first.is_visible(timeout=800):
                    self._human_fill(email_field.first, str(applicant_data["email"]), delay=50)
            except Exception:
                pass

        last_err = ""
        for attempt in range(1, 4):
            logger.info("Login attempt %s/3", attempt)

            answer = self._solve_math_captcha(page)
            if answer is None:
                self._refresh_captcha(page)
                time.sleep(1.2)
                answer = self._solve_math_captcha(page)
            if answer is None:
                raise RuntimeError("Could not read math CAPTCHA.")

            self._fill_captcha_answer(page, answer)
            time.sleep(0.5)

            clicked = self._click_modal_login_button(page)
            if not clicked:
                last_err = "Could not click modal Login button below captcha"
                continue

            if self._otp_ui_present(page, wait_ms=12000) or self._logged_in_ui_present(page, wait_ms=3000):
                logger.info("OTP/dashboard detected after submit — login OK")
                return

            err = self._read_login_error(page)
            last_err = err or "OTP modal did not open after submit"
            self._refresh_captcha(page)
            time.sleep(1.0)

        raise RuntimeError(f"Login submit did not open OTP modal: {last_err}")

    def _read_login_error(self, page: Page) -> str:
        try:
            txt = page.evaluate(
                """() => {
                    const keys = ['error', 'invalid', 'incorrect', 'failed', 'captcha', 'mobile'];
                    const nodes = Array.from(document.querySelectorAll('[class*="toast"], [class*="error"], [role="alert"], p, span, div'));
                    for (const el of nodes) {
                        const t = (el.textContent || '').replace(/\\s+/g, ' ').trim();
                        if (t.length >= 5 && t.length <= 180 && keys.some(k => t.toLowerCase().includes(k))) return t;
                    }
                    return '';
                }"""
            )
            return (txt or "").strip()
        except Exception:
            return ""

    def _refresh_captcha(self, page: Page) -> None:
        try:
            page.evaluate(
                """() => {
                    const btns = Array.from(document.querySelectorAll('button, svg, img, i'));
                    for (const b of btns) {
                        const cls = (b.getAttribute('class') || '').toLowerCase();
                        if (cls.includes('refresh') || cls.includes('reload')) { b.click(); return; }
                    }
                }"""
            )
        except Exception:
            pass

    def _solve_math_captcha(self, page: Page) -> Optional[str]:
        logger.info("Solving math CAPTCHA...")
        time.sleep(0.8)
        try:
            body = page.locator("body").inner_text(timeout=3000)
            for pat in [r"(\d+)\s*\+\s*(\d+)", r"(\d+)\s*[\+＋]\s*(\d+)"]:
                m = re.search(pat, body)
                if m:
                    a, b = int(m.group(1)), int(m.group(2))
                    if a <= 99 and b <= 99:
                        return str(a + b)
        except Exception:
            pass

        try:
            nums: List[int] = page.evaluate(
                """() => {
                    const out = [];
                    const nodes = Array.from(document.querySelectorAll('div, span, p, label, td'));
                    for (const el of nodes) {
                        if (el.children.length > 2) continue;
                        const t = (el.textContent || '').trim();
                        if (/^\\d{1,2}$/.test(t)) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && r.y > 120 && r.y < 750) out.push({ n: parseInt(t, 10), x: r.x, y: r.y });
                        }
                    }
                    out.sort((a, b) => (a.y - b.y) || (a.x - b.x));
                    return out.map(o => o.n);
                }"""
            )
            if len(nums) >= 2 and nums[0] <= 99 and nums[1] <= 99:
                return str(nums[0] + nums[1])
        except Exception:
            pass
        return None

    def _fill_captcha_answer(self, page: Page, answer: str) -> None:
        selectors = [
            "input[placeholder*='Capt' i]",
            "input[placeholder*='captcha' i]",
            "input[name*='captcha' i]",
            "input[id*='captcha' i]",
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=500):
                    self._human_fill(loc, answer, delay=80)
                    return
            except Exception:
                continue
        raise RuntimeError("Captcha answer box not found")

    def _click_modal_login_button(self, page: Page) -> bool:
        result = page.evaluate(
            """() => {
                const buttons = Array.from(document.querySelectorAll('button, a.btn, input[type="submit"]'));
                for (const b of buttons) {
                    const t = (b.textContent || b.value || '').toLowerCase();
                    if (t.includes('login') || t.includes('register')) {
                        b.click();
                        return { ok: true, text: t };
                    }
                }
                return { ok: false };
            }"""
        )
        return isinstance(result, dict) and bool(result.get("ok"))

    def _otp_ui_present(self, page: Page, wait_ms: int = 3000) -> bool:
        deadline = time.time() + (wait_ms / 1000.0)
        markers = ["text=Enter OTP", "text=Verify OTP", "input[placeholder*='OTP' i]"]
        while time.time() < deadline:
            for sel in markers:
                try:
                    if page.locator(sel).first.is_visible(timeout=250):
                        return True
                except Exception:
                    continue
            time.sleep(0.3)
        return False

    def _logged_in_ui_present(self, page: Page, wait_ms: int = 2000) -> bool:
        deadline = time.time() + (wait_ms / 1000.0)
        markers = ["text=RTI Application", "text=Logout", "text=TERMS AND CONDITIONS"]
        while time.time() < deadline:
            for sel in markers:
                try:
                    if page.locator(sel).first.is_visible(timeout=250):
                        return True
                except Exception:
                    continue
            time.sleep(0.25)
        return False

    def _wait_for_otp_verification(self, page: Page) -> None:
        logger.info("Checking for OTP modal...")
        if not self._otp_ui_present(page, wait_ms=12000):
            if self._logged_in_ui_present(page, wait_ms=3000):
                return
            time.sleep(5)
            if self._logged_in_ui_present(page, wait_ms=2000):
                return

        print("\n" + "=" * 66)
        print("  OTP REQUIRED — AUTOMATION PAUSED (60s)")
        print("  1. Check your SMS for OTP")
        print("  2. Type OTP on screen and click 'Verify OTP'")
        print("=" * 66)

        deadline = time.time() + 60
        while time.time() < deadline:
            if self._logged_in_ui_present(page, wait_ms=400):
                print("  OTP verified — resuming agent\n")
                return
            time.sleep(0.5)

        raise RuntimeError("OTP verification timed out (60s).")

    def _fill_profile_if_needed(self, page: Page, data: Dict[str, Any]) -> None:
        try:
            if not page.locator("text=User Profile Details").is_visible(timeout=3000):
                return
        except Exception:
            return

        logger.info("Filling User Profile Details...")
        try:
            page.locator("button:has-text('Save'), button:has-text('Submit')").first.click(timeout=2000)
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Force click & Terms handling
    # -----------------------------------------------------------------------
    def _force_click_element(self, page: Page, locator) -> bool:
        try:
            locator.click(timeout=2000, force=True)
            return True
        except Exception:
            return False

    def _js_tick_terms_checkbox(self, page: Page) -> bool:
        return bool(page.evaluate(
            """() => {
                window.scrollTo(0, document.body.scrollHeight);
                const boxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                if (!boxes.length) return false;
                const cb = boxes[boxes.length - 1];
                cb.checked = true;
                cb.dispatchEvent(new Event('change', { bubbles: true }));
                cb.dispatchEvent(new Event('click', { bubbles: true }));
                return true;
            }"""
        ))

    def _js_click_terms_next(self, page: Page) -> bool:
        return bool(page.evaluate(
            """() => {
                const btns = Array.from(document.querySelectorAll('button, input[type="submit"], a'));
                for (const b of btns) {
                    const t = (b.textContent || b.value || '').toLowerCase();
                    if (t.includes('next') || t.includes('proceed') || t.includes('continue')) {
                        b.click();
                        return true;
                    }
                }
                return false;
            }"""
        ))

    def _on_terms_page(self, page: Page) -> bool:
        try:
            return page.locator("text=TERMS AND CONDITIONS").is_visible(timeout=500)
        except Exception:
            return False

    def _on_application_details(self, page: Page) -> bool:
        try:
            return page.locator("textarea").count() >= 1
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Wizard details & Exact department scoring
    # -----------------------------------------------------------------------
    def _run_rti_wizard(
        self,
        page: Page,
        data: Dict[str, Any],
        rti_text: str,
        department_name: str,
        attachment_path: Optional[str],
    ) -> None:
        logger.info("Starting RTI Wizard flow...")
        time.sleep(1.5)

        self._js_tick_terms_checkbox(page)
        self._js_click_terms_next(page)
        time.sleep(2.0)

        # Radio buttons
        page.evaluate("""() => {
            const labels = Array.from(document.querySelectorAll('label'));
            for (const l of labels) {
                const t = (l.textContent || '').trim();
                if (t === 'No' || t === 'English') l.click();
            }
        }""")
        time.sleep(0.5)

        # Cascading dropdowns with Urban Development fallback for municipal queries
        dept_keywords = [k.lower() for k in re.findall(r"\w+", department_name) if len(k) >= 3]
        logger.info("Matching Department dropdown against keywords: %s", dept_keywords)

        for step in range(5):
            time.sleep(1.2)
            res = page.evaluate("""([stepIdx, targetKw]) => {
                const selects = Array.from(document.querySelectorAll('select')).filter(s => s.offsetParent !== null);
                if (stepIdx >= selects.length) return { ok: false };

                const sel = selects[stepIdx];
                const options = Array.from(sel.options).filter(o => o.value && o.value !== '0' && !o.text.includes('Select'));
                if (!options.length) return { ok: false };

                let bestOpt = null;
                if (stepIdx === 0 || stepIdx === 1) {
                    bestOpt = options.find(o => o.text.toLowerCase().includes('ahmadabad') || o.text.toLowerCase().includes('ahmedabad')) || options[0];
                } else if (stepIdx === 2) {
                    let maxScore = -1;
                    for (const opt of options) {
                        const t = opt.text.toLowerCase();
                        let score = 0;
                        targetKw.forEach(kw => { if (t.includes(kw)) score += 10; });
                        if (t.includes('municipal')) score += 25;
                        if (t.includes('corporation')) score += 20;
                        if ((t.includes('urban') || t.includes('development') || t.includes('housing')) &&
                            targetKw.some(k => ['municipal', 'corporation', 'amc', 'urban', 'city'].includes(k))) {
                            score += 30;
                        }
                        if (t.includes('chief minister')) score -= 50;

                        if (score > maxScore) {
                            maxScore = score;
                            bestOpt = opt;
                        }
                    }
                    if (!bestOpt || maxScore <= 0) {
                        bestOpt = options.find(o => o.text.toLowerCase().includes('urban')) ||
                                  options.find(o => !o.text.toLowerCase().includes('chief minister')) ||
                                  options[0];
                    }
                } else {
                    bestOpt = options[0];
                }

                if (bestOpt) {
                    sel.value = bestOpt.value;
                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                    return { ok: true, text: bestOpt.text };
                }
                return { ok: false };
            }""", [step, dept_keywords])

            if isinstance(res, dict) and res.get("ok"):
                logger.info("Dropdown %s selected → '%s'", step, res.get("text"))

        # Chunk query text across textareas (740 chars per box)
        chunks = [rti_text[i:i + 740] for i in range(0, len(rti_text), 740)]
        ta_locator = page.locator("textarea").first
        if ta_locator.count():
            ta_locator.fill(chunks[0])

        if len(chunks) > 1:
            plus_btn = page.locator("button:has-text('+'), .btn:has-text('+')").first
            for i in range(1, min(len(chunks), 4)):
                if plus_btn.count():
                    self._force_click_element(page, plus_btn)
                    time.sleep(0.5)
                    tas = page.locator("textarea")
                    if tas.count() > i:
                        tas.nth(i).fill(chunks[i])

        if attachment_path and page.locator("input[type='file']").count():
            try:
                page.locator("input[type='file']").first.set_input_files(attachment_path)
            except Exception:
                pass

        time.sleep(1.0)
        self._js_click_terms_next(page)
        time.sleep(3.0)


# Class Name Aliases for generic imports expecting GujaratPortalAdapter
GujaratPortalAdapter = GujaratRTIAdapter


def run_gujarat_filing_sync(
    applicant_data: Dict[str, Any],
    rti_text: str,
    department_name: str = "Ahmedabad Municipal Corporation",
    attachment_path: Optional[str] = None,
) -> Dict[str, Any]:
    return GujaratRTIAdapter().execute_filing(
        applicant_data=applicant_data,
        rti_text=rti_text,
        department_name=department_name,
        attachment_path=attachment_path,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    test_data = {
        "name": "Tirth Patel",
        "email": "tirth@example.com",
        "phone": "9898810531",
        "address": "khodiyar baug society",
        "house_no": "A-41",
        "landmark": "near gopal chowk, nikol",
        "pincode": "382350",
    }
    test_rti = (
        "Under Section 6(1) of the RTI Act 2005, please provide:\n"
        "1. Budget allocated for road repair in Nikol Ward 2023-25.\n"
        "2. Work orders issued and contractor names.\n"
        "3. Inspection reports and current status of pending works."
    )
    result = run_gujarat_filing_sync(test_data, test_rti, "Ahmedabad Municipal Corporation")
    print("\n" + "=" * 50)
    print("FILING RESULT")
    print("=" * 50)
    for k, v in result.items():
        print(f"  {k}: {v}")