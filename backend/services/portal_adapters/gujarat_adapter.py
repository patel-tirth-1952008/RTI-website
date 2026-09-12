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
import re
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
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


class GujaratRTIAdapter:
    """Driver for live Gujarat RTI portal (OTP + multi-step wizard)."""

    def __init__(self, debug: bool = getattr(settings, "DEBUG", True)):
        self.debug = debug
        self.portal_url = "https://onlinerti.gujarat.gov.in/rti_portal/"

    # Convenience method aliases for API callers expecting different names
    def file_rti(self, *args, **kwargs) -> Dict[str, Any]:
        return self.execute_filing(*args, **kwargs)

    def submit(self, *args, **kwargs) -> Dict[str, Any]:
        return self.execute_filing(*args, **kwargs)

    def run(self, *args, **kwargs) -> Dict[str, Any]:
        return self.execute_filing(*args, **kwargs)

    # -----------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # -----------------------------------------------------------------------
    def execute_filing(
        self,
        applicant_data: Dict[str, Any],
        rti_text: str,
        department_name: str = "Ahmedabad Municipal Corporation",
        attachment_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(f"Starting Gujarat RTI automation → Target Department: '{department_name}'")

        headless_setting = False if self.debug else True
        captured = {"payment_url": None, "registration_number": None}

        launch_args = getattr(
            settings,
            "CHROMIUM_LOW_MEM_FLAGS",
            ["--no-sandbox", "--disable-setuid-sandbox"],
        ).copy()

        if "--disable-blink-features=AutomationControlled" not in launch_args:
            launch_args.append("--disable-blink-features=AutomationControlled")

        if self.debug:
            launch_args.append("--start-maximized")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless_setting,
                slow_mo=30 if self.debug else 0,
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
            if self.debug:
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

            def on_request(req: Request):
                u = req.url.lower()
                if "failpayment" in u or u.endswith(".png") or u.endswith(".jpg"):
                    return
                if any(
                    k in u
                    for k in (
                        "payment",
                        "sbi",
                        "egras",
                        "treasury",
                        "billdesk",
                        "payu",
                        "razorpay",
                        "checkout",
                        "pg",
                    )
                ):
                    logger.info(f"Payment gateway intercepted: {req.url}")
                    captured["payment_url"] = req.url

            page.on("request", on_request)

            try:
                logger.info(f"Navigating to {self.portal_url}")
                page.goto(self.portal_url, wait_until="domcontentloaded", timeout=60000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                time.sleep(1.2)

                self._click_login_register(page)
                self._fill_login_form(page, applicant_data)
                self._wait_for_otp_verification(page)
                self._fill_profile_if_needed(page, applicant_data)
                self._run_rti_wizard(
                    page, applicant_data, rti_text, department_name, attachment_path
                )

                final_url = captured["payment_url"] or page.url
                logger.info(f"Finished. Final Payment/Portal URL = {final_url}")

                try:
                    txt = page.content()
                    m = re.search(
                        r"(RTI/[A-Z0-9]+/\d{4}/\d+|GUJ/RTI/\d+|\b\d{4}/\d+\b)", txt
                    )
                    if m:
                        captured["registration_number"] = m.group(0)
                except Exception:
                    pass

                return {
                    "success": True,
                    "portal_name": "Gujarat State RTI Portal",
                    "payment_url": final_url,
                    "registration_number": captured["registration_number"],
                    "status": "PAYMENT_PENDING" if captured["payment_url"] or "create" not in final_url else "DRAFTED",
                    "message": f"RTI drafted successfully for '{department_name}' on Gujarat portal. Pay ₹10 official fee via the gateway link.",
                }

            except Exception as exc:
                logger.exception("Automation failed")
                try:
                    page.screenshot(path="gujarat_debug_error.png", full_page=True)
                    logger.info("Saved screenshot → gujarat_debug_error.png")
                except Exception:
                    pass
                if self.debug:
                    print("\nBrowser staying open 15s for inspection...\n")
                    time.sleep(15)
                return {
                    "success": False,
                    "portal_name": "Gujarat State RTI Portal",
                    "payment_url": self.portal_url,
                    "registration_number": None,
                    "error": str(exc),
                    "message": f"Stopped on Gujarat portal: {exc}",
                }
            finally:
                browser.close()

    # -----------------------------------------------------------------------
    # Human-like input fill
    # -----------------------------------------------------------------------
    def _human_fill(self, locator, value: str, delay: int = 80) -> None:
        """Native Playwright type command with delays (bypasses bot detection)."""
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
                if loc.count() == 0:
                    continue
                if not loc.is_visible(timeout=2000):
                    continue
                box = loc.bounding_box()
                if box and box["y"] > 120:
                    continue
                try:
                    loc.scroll_into_view_if_needed(timeout=2000)
                except Exception:
                    pass
                loc.click(timeout=3000)
                clicked = True
                logger.info(f"Clicked header Login/Register using: {sel}")
                time.sleep(1.0)
                break
            except Exception:
                continue

        if not clicked:
            logger.warning("Selectors missed — coordinate click on top-right header")
            page.mouse.click(1250, 40)
            time.sleep(1.0)

        try:
            page.locator(mobile_selector).first.wait_for(state="visible", timeout=12000)
            logger.info("Login / Register modal is open and mobile field is ready.")
        except PlaywrightTimeout:
            logger.warning("Mobile field not visible — JS fallback on header Login")
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
            logger.info("Login / Register modal is open and mobile field is ready.")

    # -----------------------------------------------------------------------
    # Login form: mobile → captcha → modal submit
    # -----------------------------------------------------------------------
    def _fill_login_form(self, page: Page, applicant_data: Dict[str, Any]) -> None:
        phone = re.sub(r"\D", "", str(applicant_data.get("phone", "")))[-10:]
        if len(phone) != 10:
            raise RuntimeError(f"Invalid mobile number (need 10 digits): {phone!r}")
        logger.info(f"Filling mobile number: {phone}")

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
            logger.info(f"Login attempt {attempt}/3")

            answer = self._solve_math_captcha(page)
            if answer is None:
                logger.warning("Captcha unreadable — refreshing once")
                self._refresh_captcha(page)
                time.sleep(1.2)
                answer = self._solve_math_captcha(page)
            if answer is None:
                raise RuntimeError("Could not read math CAPTCHA. See gujarat_debug_error.png")

            self._fill_captcha_answer(page, answer)
            time.sleep(0.5)

            clicked = self._click_modal_login_button(page)
            if not clicked:
                logger.error("Modal submit button was NOT clicked")
                try:
                    page.screenshot(path=f"gujarat_login_no_submit_{attempt}.png")
                except Exception:
                    pass
                last_err = "Could not find/click modal Login button below captcha"
                continue

            logger.info(f"Submitted login form (attempt {attempt})")

            if self._otp_ui_present(page, wait_ms=12000) or self._logged_in_ui_present(page, wait_ms=3000):
                logger.info("OTP/dashboard detected after submit — login OK")
                return

            err = self._read_login_error(page)
            last_err = err or "OTP modal did not open after submit"
            logger.warning(f"After submit: {last_err}")

            try:
                page.screenshot(path=f"gujarat_login_attempt_{attempt}.png")
            except Exception:
                pass

            captcha_bad = bool(
                err and re.search(r"captcha|invalid\s*code|resolve\s*the\s*captcha|incorrect", err, re.I)
            )
            if captcha_bad or not err:
                logger.info("Refreshing captcha for next attempt")
                self._refresh_captcha(page)
                time.sleep(1.0)
            else:
                logger.error(f"Portal rejected login: {err}")
                if attempt >= 2:
                    break
                time.sleep(1.0)

        raise RuntimeError(
            "Login submit did not open OTP modal. "
            f"Last status: {last_err}. "
            "Check gujarat_login_attempt_*.png — captcha/mobile may be rejected, "
            "or modal submit was not clicked."
        )

    def _read_login_error(self, page: Page) -> str:
        try:
            txt = page.evaluate(
                """() => {
                    const keys = ['error', 'invalid', 'incorrect', 'failed', 'not valid',
                                  'captcha', 'mobile', 'register', 'try again', 'mismatch'];
                    const nodes = Array.from(document.querySelectorAll(
                        '[class*="toast"], [class*="error"], [class*="alert"], [class*="message"],
                        [role="alert"], .swal2-html-container, .Toastify, p, span, div, li'
                    ));
                    for (const el of nodes) {
                        if (el.children && el.children.length > 4) continue;
                        const t = (el.textContent || '').replace(/\\s+/g, ' ').trim();
                        if (t.length < 5 || t.length > 180) continue;
                        const r = el.getBoundingClientRect();
                        if (r.width < 40 || r.height < 10 || !r.height) continue;
                        const low = t.toLowerCase();
                        if (keys.some(k => low.includes(k))) return t;
                    }
                    return '';
                }"""
            )
            return (txt or "").strip()
        except Exception:
            return ""

    def _refresh_captcha(self, page: Page) -> None:
        js_clicked = page.evaluate(
            """() => {
                const label = Array.from(document.querySelectorAll('*')).find(el => {
                    const t = (el.textContent || '').trim();
                    return t === 'Resolve the captcha' || t === 'Resolve the Captcha';
                });
                const candidates = Array.from(document.querySelectorAll(
                    'button, [role="button"], svg, img, i, span'
                ));
                const labY = label ? label.getBoundingClientRect().y : 300;
                const labX = label ? label.getBoundingClientRect().x : 400;

                for (const el of candidates) {
                    const r = el.getBoundingClientRect();
                    if (r.width < 8 || r.width > 48 || r.height < 8 || r.height > 48) continue;
                    if (Math.abs(r.y - labY) > 80) continue;
                    if (r.x < labX - 20) continue;
                    const cls = (el.getAttribute('class') || '').toLowerCase();
                    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                    const alt = (el.getAttribute('alt') || '').toLowerCase();
                    const title = (el.getAttribute('title') || '').toLowerCase();
                    const hint = cls + ' ' + aria + ' ' + alt + ' ' + title;
                    const isRefresh = hint.includes('refresh') || hint.includes('reload') || hint.includes('rotate') || (el.tagName === 'SVG' || el.querySelector('svg'));

                    if (isRefresh || (r.width <= 40 && r.x > labX + 80)) {
                        const clickable = el.closest('button, [role="button"]') || el;
                        const t = (clickable.textContent || '').toLowerCase();
                        if (t.includes('login') || t.includes('register') || t.includes('verify')) continue;
                        clickable.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        return true;
                    }
                }
                return false;
            }"""
        )
        if js_clicked:
            logger.info("Clicked captcha refresh (icon near captcha)")
            time.sleep(0.8)
            return

        for sel in [
            "[class*='refresh' i]",
            "[aria-label*='refresh' i]",
            "img[alt*='refresh' i]",
            "button[title*='refresh' i]",
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible(timeout=600):
                    txt = (loc.inner_text(timeout=400) or "").lower()
                    if "login" in txt or "register" in txt:
                        continue
                    loc.click(timeout=1200)
                    logger.info(f"Clicked captcha refresh via: {sel}")
                    time.sleep(0.8)
                    return
            except Exception:
                continue
        logger.warning("Captcha refresh icon not found — leaving current captcha")

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
                        ans = str(a + b)
                        logger.info(f"CAPTCHA via text: {a} + {b} = {ans}")
                        return ans
        except Exception:
            pass

        try:
            nums: List[int] = page.evaluate(
                """() => {
                    const out = [];
                    const nodes = Array.from(document.querySelectorAll('div, span, p, label, td, li'));
                    for (const el of nodes) {
                        if (el.children.length > 2) continue;
                        const t = (el.textContent || '').trim();
                        if (!/^\\d{1,2}$/.test(t)) continue;
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.width < 90 && r.height > 0 && r.height < 70 && r.y > 120 && r.y < 750 && r.x > 200 && r.x < 1100) {
                            out.push({ n: parseInt(t, 10), x: r.x, y: r.y });
                        }
                    }
                    out.sort((a, b) => (a.y - b.y) || (a.x - b.x));
                    if (out.length < 2) return out.map(o => o.n);
                    const rowY = out[0].y;
                    const same = out.filter(o => Math.abs(o.y - rowY) < 30);
                    same.sort((a, b) => a.x - b.x);
                    return same.map(o => o.n);
                }"""
            )
            if len(nums) >= 2 and nums[0] <= 99 and nums[1] <= 99:
                ans = str(nums[0] + nums[1])
                logger.info(f"CAPTCHA via DOM: {nums[0]} + {nums[1]} = {ans} (candidates={nums})")
                return ans
        except Exception as e:
            logger.debug(f"DOM captcha: {e}")

        logger.warning("Could not parse math CAPTCHA")
        return None

    def _fill_captcha_answer(self, page: Page, answer: str) -> None:
        logger.info(f"Filling captcha answer: {answer}")
        selectors = [
            "input[placeholder*='Capt' i]",
            "input[placeholder*='captcha' i]",
            "input[name*='captcha' i]",
            "input[id*='captcha' i]",
            "div:has-text('Resolve the captcha') input[type='text']",
            "div:has-text('Resolve the captcha') input:not([type='hidden']):not([type='tel'])",
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel)
                for i in range(loc.count()):
                    inp = loc.nth(i)
                    if not inp.is_visible():
                        continue
                    ph = (inp.get_attribute("placeholder") or "").lower()
                    nm = (inp.get_attribute("name") or "").lower()
                    if "mobile" in ph or "email" in ph or "otp" in ph:
                        continue
                    if "mobile" in nm:
                        continue
                    box = inp.bounding_box()
                    if box and box["width"] > 280:
                        continue
                    self._human_fill(inp, answer, delay=80)
                    logger.info(f"Captcha filled via: {sel}")
                    return
            except Exception:
                continue
        raise RuntimeError("Captcha answer box not found")

    def _click_modal_login_button(self, page: Page) -> bool:
        logger.info("Clicking modal submit (Login/Register BELOW captcha)...")
        result = page.evaluate(
            """() => {
                const normalize = (s) => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                let captchaY = 0;
                const all = Array.from(document.querySelectorAll('div, span, label, p, h1, h2, h3, h4'));
                for (const el of all) {
                    const t = normalize(el.textContent);
                    if (t === 'resolve the captcha' || t.includes('resolve the captcha')) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.y > 80) captchaY = Math.max(captchaY, r.y);
                    }
                }
                const inputs = Array.from(document.querySelectorAll('input'));
                for (const inp of inputs) {
                    const ph = normalize(inp.getAttribute('placeholder'));
                    const nm = normalize(inp.getAttribute('name'));
                    if (ph.includes('capt') || nm.includes('capt')) {
                        const r = inp.getBoundingClientRect();
                        if (r.y > captchaY) captchaY = r.y;
                    }
                }
                if (!captchaY) captchaY = 280;

                const buttons = Array.from(document.querySelectorAll('button, a.btn, input[type="submit"], [role="button"]'));
                const scored = [];
                for (const b of buttons) {
                    const t = normalize(b.textContent || b.value || '');
                    const r = b.getBoundingClientRect();
                    if (r.width < 40 || r.height < 18 || r.y < 90 || (r.width <= 48 && r.height <= 48)) continue;
                    if (t.includes('verify') && t.includes('otp')) continue;
                    if (t.includes('refresh') || t.includes('resend')) continue;

                    const isLogin = t === 'login / register' || t === 'login/register' || t === 'login' || (t.includes('login') && t.includes('register')) || (b.getAttribute('type') === 'submit' && t.includes('login'));
                    if (!isLogin) continue;

                    let score = 0;
                    if (r.y > captchaY + 10) score += 50;
                    if (r.y > captchaY - 5) score += 20;
                    if (t.includes('login') && t.includes('register')) score += 30;
                    if (b.tagName === 'BUTTON') score += 10;
                    if (b.getAttribute('type') === 'submit') score += 15;
                    if (r.x > 200 && r.x < 1000) score += 5;
                    if (r.width > 100) score += 10;
                    scored.push({ el: b, score, t, y: r.y, x: r.x, w: r.width });
                }

                scored.sort((a, b) => b.score - a.score);
                if (!scored.length || scored[0].y < 100) return { ok: false };

                const best = scored[0];
                best.el.scrollIntoView({ block: 'center', inline: 'center' });
                if (best.el.disabled) {
                    best.el.disabled = false;
                    best.el.removeAttribute('disabled');
                    best.el.setAttribute('aria-disabled', 'false');
                }
                best.el.click();
                return { ok: true, text: best.t, y: Math.round(best.y), score: best.score, w: Math.round(best.w) };
            }"""
        )

        if isinstance(result, dict) and result.get("ok"):
            logger.info(
                f"Modal submit clicked via geometry JS (text={result.get('text')!r}, y={result.get('y')})"
            )
            time.sleep(1.2)
            return True
        return False

    def _otp_ui_present(self, page: Page, wait_ms: int = 3000) -> bool:
        deadline = time.time() + (wait_ms / 1000.0)
        markers = [
            "text=Please Enter OTP",
            "text=Enter OTP",
            "text=One Time Password",
            "text=Verify OTP",
            "button:has-text('Verify OTP')",
            "input[placeholder*='OTP' i]",
            "input[placeholder*='Enter OTP' i]",
            "text=registered mobile number",
            "text=OTP has been sent",
            "text=otp has been sent",
        ]
        while time.time() < deadline:
            for sel in markers:
                try:
                    loc = page.locator(sel)
                    if loc.count() and loc.first.is_visible(timeout=250):
                        return True
                except Exception:
                    continue
            time.sleep(0.3)
        return False

    def _logged_in_ui_present(self, page: Page, wait_ms: int = 2000) -> bool:
        deadline = time.time() + (wait_ms / 1000.0)
        markers = [
            "text=RTI Application",
            "text=Check the Status",
            "text=Logout",
            "text=User Profile",
            "text=TERMS AND CONDITIONS",
            "a:has-text('Logout')",
            "button:has-text('Logout')",
        ]
        while time.time() < deadline:
            for sel in markers:
                try:
                    loc = page.locator(sel)
                    if loc.count() and loc.first.is_visible(timeout=250):
                        return True
                except Exception:
                    continue
            time.sleep(0.25)
        return False

    def _wait_for_otp_verification(self, page: Page) -> None:
        logger.info("Checking for OTP modal...")

        if not self._otp_ui_present(page, wait_ms=12000):
            if self._logged_in_ui_present(page, wait_ms=3000):
                logger.info("Already logged in — skipping OTP wait")
                return
            logger.info("Waiting extra 10s for OTP UI...")
            if not self._otp_ui_present(page, wait_ms=10000):
                if self._logged_in_ui_present(page, wait_ms=2000):
                    logger.info("Logged in without OTP UI")
                    return
                try:
                    page.screenshot(path="gujarat_no_otp.png", full_page=True)
                except Exception:
                    pass
                raise RuntimeError(
                    "OTP box did not appear after login. Screenshot: gujarat_no_otp.png."
                )

        try:
            page.bring_to_front()
        except Exception:
            pass

        print("\n" + "=" * 66)
        print("  OTP REQUIRED — AUTOMATION PAUSED")
        print("  1. Look at the Chrome window (OTP popup)")
        print("  2. Type the OTP from your SMS")
        print("  3. Click blue 'Verify OTP'")
        print("  Max wait: 60 seconds  |  Agent continues automatically after verify")
        print("=" * 66)

        otp_input = page.locator(
            "input[placeholder*='OTP' i], input[placeholder*='Enter OTP' i], "
            "input[name*='otp' i], input[id*='otp' i]"
        ).first
        try:
            if otp_input.count():
                otp_input.click(timeout=2000)
        except Exception:
            pass

        deadline = time.time() + 60
        last_printed = 61

        while time.time() < deadline:
            remaining = int(deadline - time.time())
            if remaining != last_printed and remaining % 5 == 0:
                print(f"  … waiting for OTP verify  ({remaining}s left)")
                last_printed = remaining
            try:
                vb = page.locator("button:has-text('Verify OTP'), button:has-text('Verify')")
                verify_btn_visible = vb.count() > 0 and vb.first.is_visible(timeout=200)
                otp_text_gone = page.locator("text=Please Enter OTP").count() == 0
                logged_in = self._logged_in_ui_present(page, wait_ms=400)

                if logged_in or (
                    otp_text_gone
                    and not verify_btn_visible
                    and not self._otp_ui_present(page, wait_ms=400)
                ):
                    print("  OTP verified — resuming agent\n")
                    logger.info("OTP verified successfully — resuming")
                    time.sleep(2.0)
                    return
            except Exception:
                pass
            time.sleep(0.5)

        raise RuntimeError("OTP not verified within 60 seconds.")

    def _fill_profile_if_needed(self, page: Page, data: Dict[str, Any]) -> None:
        try:
            visible = page.locator("text=User Profile Details").is_visible(timeout=5000)
        except Exception:
            visible = False
        if not visible:
            logger.info("Profile already complete — skipping")
            return

        logger.info("Filling User Profile Details...")

        def fill_label(label_part: str, value: str):
            try:
                lab = page.locator(f"label:has-text('{label_part}')").first
                if not lab.count():
                    return
                inp = lab.locator("xpath=following::input[1]")
                if not inp.count():
                    inp = lab.locator("..").locator("input").first
                if inp.count():
                    self._human_fill(inp.first, str(value), delay=50)
            except Exception:
                pass

        fill_label("Full name", data.get("name", "Citizen"))
        fill_label("Pincode", data.get("pincode", "382350"))
        fill_label("Flat no", data.get("house_no", "A-41"))
        fill_label("Street", data.get("address", "khodiyar baug society"))
        fill_label("Landmark", data.get("landmark", "near gopal chowk, nikol"))

        try:
            page.locator("label:has-text('Male')").first.click(timeout=2000)
        except Exception:
            pass

        try:
            sels = page.locator("select")
            mapping = [(0, "INDIA"), (1, "GUJARAT"), (2, "AHMEDABAD"), (3, "AHMEDABAD")]
            for idx, label in mapping:
                if sels.count() > idx:
                    sels.nth(idx).select_option(label=label)
                    time.sleep(0.35)
        except Exception as e:
            logger.warning(f"Profile dropdowns: {e}")

        save = page.locator(
            "button:has-text('Save'), button:has-text('Update'), button:has-text('Submit')"
        )
        if save.count() and save.first.is_visible():
            self._force_click_element(page, save.first)
            time.sleep(2)
            logger.info("Profile saved")

    # -----------------------------------------------------------------------
    # Force click helpers
    # -----------------------------------------------------------------------
    def _force_click_element(self, page: Page, locator) -> bool:
        """Click without Playwright visibility scroll (avoids 30s hangs)."""
        try:
            box = locator.bounding_box(timeout=2000)
            if box and box.get("width", 0) > 2 and box.get("height", 0) > 2:
                x = box["x"] + box["width"] / 2
                y = box["y"] + box["height"] / 2
                page.mouse.move(x, y)
                time.sleep(0.15)
                page.mouse.click(x, y)
                return True
        except Exception:
            pass
        try:
            locator.click(timeout=2000, force=True)
            return True
        except Exception:
            pass
        try:
            locator.evaluate(
                """el => {
                    el.scrollIntoView({block:'center', inline:'center'});
                    if (el.disabled) { el.disabled = false; el.removeAttribute('disabled'); }
                    el.click();
                }"""
            )
            return True
        except Exception:
            return False

    def _js_tick_terms_checkbox(self, page: Page) -> bool:
        """Human-like: scroll bottom, tick last/agree checkbox with React events."""
        result = page.evaluate(
            """() => {
                window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' });
                const scrollables = Array.from(document.querySelectorAll('div, section, main, form'))
                    .filter(el => el.scrollHeight > el.clientHeight + 40);
                for (const s of scrollables) {
                    try { s.scrollTop = s.scrollHeight; } catch (e) {}
                }

                const boxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                if (!boxes.length) return { ok: false, reason: 'no-checkbox' };

                let target = boxes[boxes.length - 1];
                for (const cb of boxes) {
                    let root = cb.parentElement;
                    for (let i = 0; i < 5 && root; i++) {
                        const t = (root.textContent || '').toLowerCase();
                        if (t.includes('i agree') || t.includes('terms') || t.includes('declaration') || t.includes('guidelines')) {
                            target = cb;
                            break;
                        }
                        root = root.parentElement;
                    }
                }

                target.scrollIntoView({ block: 'center', inline: 'nearest' });

                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'checked'
                ).set;
                nativeInputValueSetter.call(target, true);
                target.checked = true;
                target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                target.dispatchEvent(new Event('input', { bubbles: true }));
                target.dispatchEvent(new Event('change', { bubbles: true }));

                const id = target.getAttribute('id');
                if (id) {
                    const lab = document.querySelector('label[for="' + id + '"]');
                    if (lab) lab.click();
                } else {
                    const lab = target.closest('label');
                    if (lab) lab.click();
                }

                return { ok: true, checked: !!target.checked };
            }"""
        )
        ok = bool(isinstance(result, dict) and result.get("ok"))
        if ok:
            logger.info("Checked Terms & Conditions checkbox (JS/React events).")
        else:
            logger.warning(f"Terms checkbox JS tick failed: {result}")
        return ok

    def _js_click_terms_next(self, page: Page) -> bool:
        """Find and click Next after terms — pure JS, no Playwright visibility."""
        result = page.evaluate(
            """() => {
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();

                window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' });

                const nodes = Array.from(document.querySelectorAll(
                    'button, a, input[type="submit"], input[type="button"], [role="button"], .s-next, .btn-theme'
                ));

                const scored = [];
                for (const el of nodes) {
                    const t = norm(el.textContent || el.value || el.getAttribute('aria-label') || '');
                    const cls = (el.getAttribute('class') || '').toLowerCase();
                    const r = el.getBoundingClientRect();

                    if (r.width < 20 && r.height < 20) continue;

                    let score = 0;
                    if (cls.includes('s-next')) score += 80;
                    if (cls.includes('btn-theme') && t.includes('next')) score += 60;
                    if (t === 'next') score += 70;
                    if (t.includes('next')) score += 40;
                    if (t.includes('proceed')) score += 35;
                    if (t.includes('continue')) score += 30;
                    if (t.includes('i agree') || t === 'agree') score += 25;
                    if (t.includes('submit') && !t.includes('login')) score += 15;
                    if (t.includes('payment') || t.includes('make payment')) score += 80;

                    if (r.y > 200) score += 20;
                    if (r.y > 400) score += 15;
                    if (r.width >= 60) score += 10;
                    if (el.tagName === 'BUTTON') score += 8;

                    if (t.includes('login') || t.includes('register') || t.includes('logout')) score -= 100;
                    if (t.includes('verify') && t.includes('otp')) score -= 100;
                    if (t.includes('back') || t.includes('previous') || t.includes('cancel')) score -= 50;
                    if (t.includes('refresh') || t.includes('resend')) score -= 50;

                    if (score < 20) continue;
                    scored.push({
                        el, score, t, cls,
                        y: r.y, x: r.x, w: r.width, h: r.height,
                        disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true')
                    });
                }

                scored.sort((a, b) => b.score - a.score || b.y - a.y);
                if (!scored.length) return { ok: false, reason: 'no-candidate' };

                const best = scored[0];
                const el = best.el;

                try {
                    el.disabled = false;
                    el.removeAttribute('disabled');
                    el.setAttribute('aria-disabled', 'false');
                    el.classList.remove('disabled');
                } catch (e) {}

                el.scrollIntoView({ block: 'center', inline: 'center' });

                const r2 = el.getBoundingClientRect();
                const cx = r2.x + r2.width / 2;
                const cy = r2.y + r2.height / 2;

                const opts = { bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy };
                el.dispatchEvent(new MouseEvent('mouseover', opts));
                el.dispatchEvent(new MouseEvent('mouseenter', opts));
                el.dispatchEvent(new MouseEvent('mousemove', opts));
                el.dispatchEvent(new MouseEvent('mousedown', opts));
                el.dispatchEvent(new MouseEvent('mouseup', opts));
                el.dispatchEvent(new MouseEvent('click', opts));
                try { el.click(); } catch (e) {}

                return {
                    ok: true,
                    text: best.t,
                    cls: best.cls,
                    y: Math.round(best.y),
                    score: best.score,
                    cx: Math.round(cx),
                    cy: Math.round(cy)
                };
            }"""
        )

        if isinstance(result, dict) and result.get("ok"):
            logger.info(
                f"Terms Next clicked via JS "
                f"(text={result.get('text')!r}, y={result.get('y')}, score={result.get('score')})"
            )
            try:
                cx, cy = result.get("cx"), result.get("cy")
                if cx is not None and cy is not None and cy > 0:
                    page.mouse.move(cx, cy)
                    time.sleep(0.12)
                    page.mouse.click(cx, cy)
                    logger.info(f"Also mouse-clicked Next at ({cx}, {cy})")
            except Exception:
                pass
            return True

        logger.warning(f"JS Next click found nothing: {result}")
        return False

    def _click_terms_next_with_retries(self, page: Page, max_tries: int = 6) -> bool:
        """After checkbox: try many strategies until application step appears."""
        for attempt in range(1, max_tries + 1):
            logger.info(f"Terms → Next click try {attempt}/{max_tries}")

            self._js_tick_terms_checkbox(page)
            time.sleep(0.35)

            clicked = self._js_click_terms_next(page)

            if not clicked:
                for sel in [
                    "button.s-next",
                    "button.btn-theme",
                    "button:has-text('Next')",
                    "button:has-text('Proceed')",
                    "button:has-text('Continue')",
                    "button:has-text('Submit')",
                    "[role='button']:has-text('Next')",
                    "a:has-text('Next')",
                ]:
                    try:
                        loc = page.locator(sel)
                        n = loc.count()
                        if not n:
                            continue
                        target = loc.last
                        if self._force_click_element(page, target):
                            logger.info(f"Force-clicked Next via selector: {sel}")
                            clicked = True
                            break
                    except Exception:
                        continue

            time.sleep(1.2)

            if self._on_application_details(page) or not self._on_terms_page(page):
                logger.info("Left Terms page after Next — success")
                return True

            if attempt == 3:
                try:
                    page.keyboard.press("Enter")
                    time.sleep(1.0)
                    if self._on_application_details(page) or not self._on_terms_page(page):
                        logger.info("Left Terms page via Enter key")
                        return True
                except Exception:
                    pass

            if attempt >= 4:
                try:
                    page.keyboard.press("Tab")
                    time.sleep(0.2)
                    page.keyboard.press("Tab")
                    time.sleep(0.2)
                    page.keyboard.press("Enter")
                    time.sleep(1.0)
                    if self._on_application_details(page) or not self._on_terms_page(page):
                        logger.info("Left Terms page via Tab+Enter")
                        return True
                except Exception:
                    pass

            logger.warning(f"Still on Terms after try {attempt}")

        return self._on_application_details(page) or not self._on_terms_page(page)

    def _on_terms_page(self, page: Page) -> bool:
        markers = [
            "text=TERMS AND CONDITIONS",
            "text=Guidelines For Use",
            "text=I agree that my RTI Application",
            "text=I agree",
        ]
        for sel in markers:
            try:
                loc = page.locator(sel)
                if loc.count() and loc.first.is_visible(timeout=400):
                    return True
            except Exception:
                continue
        try:
            body = page.evaluate("() => (document.body && document.body.innerText) || ''") or ""
            low = body.lower()
            if "terms and conditions" in low or "guidelines for use" in low:
                if "rti application details" in low or "applicant basic details" in low:
                    return False
                return True
        except Exception:
            pass
        return False

    def _on_application_details(self, page: Page) -> bool:
        markers = [
            "text=RTI APPLICATION DETAILS",
            "text=Applicant Basic Details",
            "text=RTI Details",
            "text=Public Authority",
            "textarea",
        ]
        for sel in markers:
            try:
                loc = page.locator(sel)
                if loc.count() and loc.first.is_visible(timeout=500):
                    return True
            except Exception:
                continue
        try:
            body = page.evaluate("() => (document.body && document.body.innerText) || ''") or ""
            low = body.lower()
            if any(
                k in low
                for k in (
                    "rti application details",
                    "applicant basic details",
                    "public authority",
                    "select department",
                )
            ):
                return True
            if page.locator("select").count() >= 1 and page.locator("textarea").count() >= 1:
                return True
        except Exception:
            pass
        return False

    def _wait_for_application_details(self, page: Page, timeout_s: float = 25.0) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self._on_application_details(page):
                return
            if self._on_terms_page(page):
                self._js_click_terms_next(page)
            time.sleep(0.8)
        logger.warning("Application details wait timed out — continuing with best-effort fill")

    # -----------------------------------------------------------------------
    # RTI wizard
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

        # -------------------------------------------------------------------
        # Step 1: Check if already auto-redirected to Terms & Conditions page
        # -------------------------------------------------------------------
        time.sleep(1.5)
        terms_visible = self._on_terms_page(page)
        if terms_visible:
            logger.info("Already on Terms & Conditions / Declaration page after OTP redirect.")
        else:
            try:
                if page.locator("input[type='checkbox']").count():
                    terms_visible = True
                    logger.info("Terms page inferred via checkbox presence.")
            except Exception:
                pass

        if not terms_visible:
            logger.info("Opening RTI Application from sidebar...")
            for sel in [
                "a:has-text('RTI Application')",
                "text=RTI Application",
                "li:has-text('RTI Application')",
                "[href*='rti' i]",
            ]:
                loc = page.locator(sel).first
                try:
                    if loc.count() and loc.is_visible(timeout=2000):
                        self._force_click_element(page, loc)
                        time.sleep(1.5)
                        break
                except Exception:
                    continue

        # -------------------------------------------------------------------
        # Accept Terms & Conditions — human path: scroll → tick → Next
        # -------------------------------------------------------------------
        logger.info("Step 1 — Handling Terms & Conditions / Declaration")

        try:
            page.wait_for_selector(
                "input[type='checkbox'], text=TERMS AND CONDITIONS, text=I agree, button.s-next",
                timeout=10000,
                state="attached",
            )
        except Exception:
            logger.warning("Terms selector wait timed out — proceeding with JS locate...")

        page.evaluate(
            """() => {
                window.scrollTo(0, 0);
                const h = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                const steps = 6;
                for (let i = 1; i <= steps; i++) {
                    window.scrollTo(0, (h * i) / steps);
                }
                window.scrollTo(0, h);
            }"""
        )
        time.sleep(0.6)

        ticked = self._js_tick_terms_checkbox(page)
        if not ticked:
            cbs = page.locator("input[type='checkbox']")
            if cbs.count():
                cb = cbs.last
                try:
                    cb.check(force=True, timeout=2000)
                    logger.info("Checked Terms checkbox via Playwright force.")
                    ticked = True
                except Exception:
                    try:
                        cb.click(force=True, timeout=2000)
                        ticked = True
                    except Exception:
                        pass
        if not ticked:
            logger.warning("Checkbox tick uncertain — still attempting Next.")

        time.sleep(0.5)

        ok = self._click_terms_next_with_retries(page, max_tries=6)
        if not ok:
            try:
                page.screenshot(path="gujarat_terms_next_stuck.png", full_page=True)
                logger.info("Saved screenshot → gujarat_terms_next_stuck.png")
            except Exception:
                pass
            logger.warning("Could not confirm leaving Terms — waiting for application markers anyway")

        time.sleep(1.0)
        self._wait_for_application_details(page, timeout_s=20.0)

        # -------------------------------------------------------------------
        # Step 2 — Fill RTI Application Details
        # -------------------------------------------------------------------
        logger.info("Step 2 — Filling RTI Application Details")

        # 2A. Click Radio Buttons via robust JS execution
        logger.info("Selecting Poverty Line 'No' & Language 'English'")
        page.evaluate("""() => {
            const labels = Array.from(document.querySelectorAll('label'));
            for (const l of labels) {
                const t = (l.textContent || '').trim();
                if (t === 'No' || t === 'English') {
                    l.scrollIntoView({block:'center'});
                    l.click();
                }
            }
        }""")
        time.sleep(0.5)

        # 2B. Fill Cascading Dropdowns: District → Taluka → Department → Office Name → Info Pertaining
        dept_keywords = [k.lower() for k in re.findall(r"\w+", department_name) if len(k) >= 3]
        logger.info(f"Matching Department dropdown against keywords: {dept_keywords}")

        for step in range(5):
            time.sleep(1.2)

            res = page.evaluate("""([stepIdx, targetKw]) => {
                const selects = Array.from(document.querySelectorAll('select'))
                    .filter(s => s.offsetParent !== null && !s.disabled);

                if (stepIdx >= selects.length) return { ok: false, msg: 'no-select-at-index' };
                const sel = selects[stepIdx];

                const options = Array.from(sel.options)
                    .filter(o => o.value && o.value !== '' && o.value !== '0' && !o.text.includes('Select'));

                if (options.length === 0) return { ok: false, msg: 'no-valid-options' };

                let bestOpt = null;

                if (stepIdx === 0 || stepIdx === 1) {
                    bestOpt = options.find(o => o.text.toLowerCase().includes('ahmadabad') || o.text.toLowerCase().includes('ahmedabad')) || options[0];
                } else if (stepIdx === 2) {
                    let maxScore = -1;
                    for (const opt of options) {
                        const t = opt.text.toLowerCase();
                        let score = 0;
                        for (const kw of targetKw) {
                            if (t.includes(kw)) score += 10;
                        }
                        if (t.includes('municipal') && targetKw.some(k => k.includes('municipal') || k.includes('amc'))) score += 20;
                        if (t.includes('corporation') && targetKw.some(k => k.includes('corporation'))) score += 15;
                        if (t.includes('ahmedabad') || t.includes('ahmadabad')) score += 5;

                        if (t.includes('chief minister') && !targetKw.some(k => k.includes('chief') || k.includes('cm'))) {
                            score -= 50;
                        }

                        if (score > maxScore) {
                            maxScore = score;
                            bestOpt = opt;
                        }
                    }
                    if (!bestOpt || maxScore <= 0) {
                        bestOpt = options.find(o => !o.text.toLowerCase().includes('chief minister')) || options[0];
                    }
                } else {
                    bestOpt = options[0];
                }

                if (bestOpt) {
                    sel.value = bestOpt.value;
                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                    return { ok: true, text: bestOpt.text, val: bestOpt.value };
                }

                return { ok: false, msg: 'selection-failed' };
            }""", [step, dept_keywords])

            if res.get("ok"):
                logger.info(f"Dropdown {step} selected → '{res.get('text')}'")
            else:
                logger.warning(f"Dropdown {step} note → {res.get('msg')}")

        # 2C. Fill Text Area safely respecting 750 character limit with '+' chunks
        logger.info("Injecting AI RTI text (Chunking max 740 chars per box)")
        chunks = [rti_text[i:i + 740] for i in range(0, len(rti_text), 740)]

        ta_locator = page.locator("textarea")
        ta_locator.first.wait_for(state="attached", timeout=15000)

        try:
            ta_locator.first.scroll_into_view_if_needed(timeout=2000)
            ta_locator.first.click(force=True, timeout=2000)
        except Exception:
            pass
        ta_locator.first.fill(chunks[0])

        if len(chunks) > 1:
            plus_btn = page.locator("button:has-text('+'), .btn:has-text('+'), i.fa-plus").first
            for i in range(1, min(len(chunks), 4)):
                if plus_btn.count():
                    logger.info(f"Adding text chunk {i + 1} via '+' button")
                    self._force_click_element(page, plus_btn)
                    time.sleep(0.5)
                    tas = page.locator("textarea")
                    if tas.count() > i:
                        tas.nth(i).fill(chunks[i])

        # 2D. File attachment
        if attachment_path:
            fi = page.locator("input[type='file']")
            if fi.count():
                fi.first.set_input_files(attachment_path)
                logger.info(f"Attached file: {attachment_path}")

        time.sleep(1.0)

        # 2E. Final Next / Make Payment
        pay_clicked = self._js_click_terms_next(page)
        if not pay_clicked:
            pay_btn = page.locator(
                "button.s-next, button:has-text('Make Payment'), button:has-text('Next'), "
                "button:has-text('Submit'), button:has-text('Proceed')"
            ).last
            self._force_click_element(page, pay_btn)

        logger.info("Clicked final Next / Make Payment button")

        try:
            page.wait_for_url(
                lambda url: any(
                    k in url.lower() for k in ("payment", "checkout", "treasury", "sbi", "egras", "payu", "billdesk")
                ),
                timeout=12000,
            )
            logger.info(f"Direct redirect to Payment URL: {page.url}")
        except Exception:
            page.wait_for_timeout(4000)


# Class Name Alias for generic imports expecting GujaratPortalAdapter
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