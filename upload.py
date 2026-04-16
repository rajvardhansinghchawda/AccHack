"""
PIEMR Assignment Upload Automation  v3
========================================
Fix: ElementNotInteractableException  →  use direct URL navigation (skip menu clicking)
Fix: Alert after upload               →  auto-accept success alert
Fix: Upload flow                      →  based on actual portal HTML structure

Requirements:
    pip install selenium webdriver-manager

Usage:
    python piemr_assignment_upload.py
"""

import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    UnexpectedAlertPresentException, NoAlertPresentException
)

# ─────────────────────────────────────────────────────
#  CONFIG  ← only edit this block
# ─────────────────────────────────────────────────────
CONFIG = {
    "login_url":  "https://accsoft.piemr.edu.in/Accsoft_PIEMR/studentLogin.aspx",
    "assign_url": "https://accsoft.piemr.edu.in/accsoft_piemr/Parents/Assignment.aspx",
    "username":   "",
    "password":   "",
    "file":       r"D:\firebox\Btech\sem5\Cocubs\AllinONeC.pdf",
    "headless":   False,
    "wait":       15,
}
# ─────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════
#  DRIVER SETUP
# ══════════════════════════════════════════════════════
def build_driver(cfg) -> webdriver.Chrome:
    opts = Options()
    if cfg["headless"]:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-notifications")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
    except Exception:
        service = Service("chromedriver")

    driver = webdriver.Chrome(service=service, options=opts)
    driver.implicitly_wait(3)
    return driver


# ══════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════
def wait_click(driver, by, value, timeout=15):
    """Wait until clickable then JS-click (avoids ElementNotInteractable)."""
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.2)
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)
    return el


def js_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.1)
    driver.execute_script("arguments[0].click();", el)


def dismiss_alert(driver, timeout=3):
    """Accept any open alert/confirm dialog. Returns alert text or None."""
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        txt = alert.text
        print(f"         [Alert] '{txt}' → OK")
        alert.accept()
        return txt
    except (TimeoutException, NoAlertPresentException):
        return None


# ══════════════════════════════════════════════════════
#  STEP 1  LOGIN
# ══════════════════════════════════════════════════════
def login(driver, cfg):
    print("\n[1] Logging in ...")
    driver.get(cfg["login_url"])
    time.sleep(2)

    # --- username ---
    for uid in [
        "ctl00_ContentPlaceHolder1_txtUserName",
        "ctl00_ContentPlaceHolder1_txtEnrollNo",
        "txtUserName", "txtEnrollNo", "txtUsername",
    ]:
        try:
            f = driver.find_element(By.ID, uid)
            f.clear(); f.send_keys(cfg["username"]); break
        except NoSuchElementException:
            continue
    else:
        driver.find_element(By.XPATH, "(//input[@type='text'])[1]").send_keys(cfg["username"])

    # --- password ---
    for pid in [
        "ctl00_ContentPlaceHolder1_txtPassword",
        "txtPassword", "txtPass",
    ]:
        try:
            f = driver.find_element(By.ID, pid)
            f.clear(); f.send_keys(cfg["password"]); break
        except NoSuchElementException:
            continue
    else:
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys(cfg["password"])

    # --- submit ---
    for bid in [
        "ctl00_ContentPlaceHolder1_btnLogin",
        "btnLogin", "btnSubmit",
    ]:
        try:
            driver.find_element(By.ID, bid).click(); break
        except NoSuchElementException:
            continue
    else:
        driver.find_element(
            By.XPATH, "//input[@type='submit'] | //button[@type='submit']"
        ).click()

    time.sleep(3)
    dismiss_alert(driver, timeout=2)
    print("    ✓ Logged in  →  " + driver.title)


# ══════════════════════════════════════════════════════
#  STEP 2  NAVIGATE DIRECTLY TO ASSIGNMENTS PAGE
#          (no menu clicking — avoids interactability issues)
# ══════════════════════════════════════════════════════
def open_assignments_page(driver, cfg):
    """Go straight to the assignments URL — zero menu interaction needed."""
    driver.get(cfg["assign_url"])
    time.sleep(2)
    dismiss_alert(driver, timeout=2)
    # wait for the subject table to appear
    WebDriverWait(driver, cfg["wait"]).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.dlTable"))
    )
    print("    ✓ Assignments page loaded")


# ══════════════════════════════════════════════════════
#  STEP 3  SCAN — find subjects with new assignments
# ══════════════════════════════════════════════════════
def scan_subjects(driver):
    """
    Returns list of:
      { subject, new_count, js_postback }
    for every row where new_count > 0.
    js_postback is the raw href value like:
      javascript:__doPostBack('ctl00$...lnkViewNewAssign','')
    We store the full ID and fire it via JS.
    """
    results = []
    rows = driver.find_elements(By.CSS_SELECTOR, "table.dlTable tr.GreenPage2")

    for row in rows:
        try:
            subject = row.find_element(
                By.XPATH, ".//span[contains(@id,'Label2')]"
            ).text.strip()

            new_count = int(
                row.find_element(
                    By.XPATH, ".//input[contains(@id,'hdnNewACount')]"
                ).get_attribute("value") or "0"
            )

            if new_count > 0:
                link = row.find_element(
                    By.XPATH, ".//a[contains(@id,'lnkViewNewAssign')]"
                )
                link_id = link.get_attribute("id")
                href    = link.get_attribute("href")   # full JS postback string

                results.append({
                    "subject":   subject,
                    "new_count": new_count,
                    "link_id":   link_id,
                    "href":      href,
                })
                print(f"    📌  {subject}  →  {new_count} new")

        except Exception as e:
            print(f"    ⚠  Row parse error: {e}")

    return results


# ══════════════════════════════════════════════════════
#  STEP 4  UPLOAD  — one assignment row at a time
# ══════════════════════════════════════════════════════
def do_upload(driver, upload_anchor, file_path):
    """
    Clicks the Upload / Re-Upload anchor, handles the file-upload modal,
    selects the file, submits, and dismisses the success alert.
    Returns True on success.
    """
    try:
        # 1. Click Upload button (JS click is safest on ASP.NET anchors)
        js_click(driver, upload_anchor)
        time.sleep(2)
        dismiss_alert(driver, timeout=1)   # dismiss any pre-upload alert

        # 2. Find file input  (may be in a modal or inline)
        file_input = None
        for _ in range(4):
            inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
            if inputs:
                file_input = inputs[0]
                break
            time.sleep(1)

        if not file_input:
            print("         ✗ No file <input> appeared.")
            return False

        # 3. Send file path (works even if input is hidden)
        file_input.send_keys(os.path.abspath(file_path))
        time.sleep(1)

        # 4. Click the submit/upload/save button
        #    Priority: visible modal button → page-level submit
        SUBMIT_XPATHS = [
            # Buttons inside a visible Bootstrap modal
            "//div[contains(@class,'modal-footer')]//button[not(contains(@class,'close') or contains(@class,'cancel'))]",
            "//div[contains(@class,'modal') and contains(@style,'block')]//input[@type='submit']",
            # Page-level ASP.NET submit
            "//input[@type='submit' and contains(translate(@value,"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'upload')]",
            "//input[@type='submit' and contains(translate(@value,"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'submit')]",
            # Generic buttons
            "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
            "'abcdefghijklmnopqrstuvwxyz'),'upload')]",
            "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
            "'abcdefghijklmnopqrstuvwxyz'),'submit')]",
            # Link-buttons
            "//a[contains(@class,'btn') and (contains(text(),'Upload')"
            " or contains(text(),'Submit') or contains(text(),'Save'))]",
        ]

        clicked = False
        for xp in SUBMIT_XPATHS:
            btns = driver.find_elements(By.XPATH, xp)
            if btns:
                js_click(driver, btns[0])
                clicked = True
                break

        if not clicked:
            print("         ✗ Could not find submit button.")
            return False

        # 5. Wait and dismiss success alert
        time.sleep(2)
        alert_text = dismiss_alert(driver, timeout=4)
        if alert_text and ("success" in alert_text.lower() or "upload" in alert_text.lower()):
            print("         ✓ Upload confirmed by alert.")
        else:
            print("         ✓ Upload submitted (no confirmation alert).")

        time.sleep(1)
        return True

    except Exception as e:
        print(f"         ✗ Upload error: {e}")
        # Try to dismiss any hanging alert
        dismiss_alert(driver, timeout=2)
        return False


# ══════════════════════════════════════════════════════
#  STEP 4  PROCESS one subject
# ══════════════════════════════════════════════════════
# def process_subject(driver, subj, file_path, cfg):
#     """
#     1. Open the 'New Assignments' list for this subject (via JS postback).
#     2. Loop: find EVERY row that still shows an 'Upload' button.
#     3. Upload file, dismiss alert, re-scan until no Upload buttons remain.
#     """
#     subject   = subj["subject"]
#     expected  = subj["new_count"]
#     link_id   = subj["link_id"]

#     print(f"\n   ┌─ {subject}  ({expected} new assignment(s))")

#     # Click 'View New Assignments' link by ID
#     try:
#         link = WebDriverWait(driver, cfg["wait"]).until(
#             EC.presence_of_element_located((By.ID, link_id))
#         )
#         js_click(driver, link)
#         time.sleep(2)
#         dismiss_alert(driver, timeout=2)
#     except Exception as e:
#         print(f"   └─ ✗ Could not open subject: {e}")
#         return 0

#     uploaded = 0
#     max_iter = expected + 5     # safety ceiling

#     for iteration in range(1, max_iter + 1):
#         # Re-scan upload buttons every iteration (DOM may update after upload)
#         all_btns = driver.find_elements(
#             By.XPATH,
#             "//a[contains(@id,'btnUpload')]"
#         )

#         # Prefer 'Upload' (first-time) over 'Re-Upload' (already submitted)
#         upload_btns  = [b for b in all_btns if b.text.strip().lower() == "upload"]
#         reupload_btns = [b for b in all_btns if "re-upload" in b.text.strip().lower()]

#         targets = upload_btns if upload_btns else reupload_btns

#         if not targets:
#             print(f"   └─ No more upload buttons  ({uploaded} uploaded).")
#             break

#         # Build a friendly label for logging
#         try:
#             parent_row = targets[0].find_element(
#                 By.XPATH, "ancestor::tr[contains(@class,'GreenPage2')]"
#             )
#             assig_no = parent_row.find_element(
#                 By.XPATH, ".//span[contains(@id,'Label4')]"
#             ).text.strip()
#             due_date = parent_row.find_element(
#                 By.XPATH, ".//span[contains(@id,'Label5')]"
#             ).text.strip()
#             label = f"Assignment #{assig_no}  due {due_date}"
#         except Exception:
#             label = f"row {iteration}"

#         print(f"   │  [{iteration}/{expected}] {label}")

#         ok = do_upload(driver, targets[0], file_path)
#         if ok:
#             uploaded += 1
#             print(f"   │  Progress: {uploaded}/{expected}")
#         else:
#             print(f"   │  Skipping this row after failure.")

#         time.sleep(1)

#     print(f"   └─ Done: {uploaded} uploaded for '{subject}'")
#     return uploaded
def process_subject(driver, subj, file_path, cfg):
    subject  = subj["subject"]
    link_id  = subj["link_id"]

    print(f"\n   ┌─ {subject}")

    def open_subject():
        """Navigate to assignments page and re-open this subject."""
        driver.get(cfg["assign_url"])
        time.sleep(2)
        dismiss_alert(driver, timeout=2)
        WebDriverWait(driver, cfg["wait"]).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.dlTable"))
        )
        link = WebDriverWait(driver, cfg["wait"]).until(
            EC.presence_of_element_located((By.ID, link_id))
        )
        js_click(driver, link)
        time.sleep(2)
        dismiss_alert(driver, timeout=2)
        # Wait for assignment rows to load
        WebDriverWait(driver, cfg["wait"]).until(
            EC.presence_of_element_located((By.XPATH, "//tr[contains(@class,'GreenPage2')]"))
        )

    # ── First open ──────────────────────────────────────────────────────────
    try:
        open_subject()
    except Exception as e:
        print(f"   └─ ✗ Could not open subject: {e}")
        return 0

    # ── Collect all button IDs upfront (before any upload changes the DOM) ──
    rows_info = []
    rows = driver.find_elements(By.XPATH, "//tr[contains(@class,'GreenPage2')]")
    for row in rows:
        try:
            assig_no = row.find_element(
                By.XPATH, ".//span[contains(@id,'Label4')]"
            ).text.strip()
            due_date = row.find_element(
                By.XPATH, ".//span[contains(@id,'Label5')]"
            ).text.strip()
            btn = row.find_element(
                By.XPATH, ".//a[contains(@id,'btnUpload')]"
            )
            # ── SKIP if already uploaded (Re-Upload = already submitted) ──
            if "re-upload" in btn.text.strip().lower():
                print(f"   │  ⏭ Assignment #{assig_no} already uploaded — skipping")
                continue

            rows_info.append({
                "assig_no": assig_no,
                "due_date": due_date,
                "btn_id":   btn.get_attribute("id"),
            })
        except NoSuchElementException:
            continue

    if not rows_info:
        print(f"   └─ No upload buttons found.")
        return 0

    print(f"   │  Found {len(rows_info)} assignment(s)")

    uploaded = 0

    for idx, info in enumerate(rows_info, 1):
        print(f"   │  [{idx}/{len(rows_info)}] Assignment #{info['assig_no']}  due {info['due_date']}")

        # ── After each upload the page redirects to AssignmentView.aspx ──
        # ── so re-open the subject page before every upload             ──
        if idx > 1:
            print(f"   │  ↩ Returning to subject page for next assignment...")
            try:
                open_subject()
            except Exception as e:
                print(f"   │  ✗ Could not re-open subject: {e}")
                continue

        # Re-locate button fresh (page was reloaded)
        try:
            btn = WebDriverWait(driver, cfg["wait"]).until(
                EC.presence_of_element_located((By.ID, info["btn_id"]))
            )
        except TimeoutException:
            print(f"   │  ⚠ Button {info['btn_id']} not found — may already be uploaded, skipping.")
            continue

        ok = do_upload(driver, btn, file_path)
        if ok:
            uploaded += 1
            # Portal redirects to AssignmentView.aspx here — that's expected
            print(f"   │  ✓ Uploaded ({uploaded}/{len(rows_info)}) — portal redirected to AssignmentView")
            time.sleep(1.5)
        else:
            print(f"   │  ✗ Failed for #{info['assig_no']}, continuing...")

    print(f"   └─ Done: {uploaded}/{len(rows_info)} uploaded for '{subject}'")
    return uploaded

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
def run(cfg):
    # Validate file
    if not cfg.get("file"):
        print("ERROR: Set CONFIG['file'] to your file path.")
        return
    if not os.path.exists(cfg["file"]):
        print(f"ERROR: File not found → {cfg['file']}")
        return

    print("=" * 58)
    print("  PIEMR Assignment Auto-Uploader  v3")
    print("=" * 58)
    print(f"  User : {cfg['username']}")
    print(f"  File : {cfg['file']}")
    print("=" * 58)

    driver = build_driver(cfg)
    total  = 0

    try:
        # ── 1. Login ──────────────────────────────────────
        login(driver, cfg)

        # ── 2. Go to assignments (DIRECT URL — no menu!) ──
        print("\n[2] Opening Assignments page ...")
        open_assignments_page(driver, cfg)

        # ── 3. Scan ───────────────────────────────────────
        print("\n[3] Scanning for new assignments ...")
        subjects = scan_subjects(driver)

        if not subjects:
            print("\n  ✅  No new assignments found — nothing to do!")

        else:
            print(f"\n[4] Uploading to {len(subjects)} subject(s) ...")

            for idx, subj in enumerate(subjects, 1):
                print(f"\n  ── Subject {idx}/{len(subjects)} " + "─" * 30)

                # Return to assignments list before each subject
                open_assignments_page(driver, cfg)
                time.sleep(0.5)

                n = process_subject(driver, subj, cfg["file"], cfg)
                total += n

        print(f"\n{'=' * 58}")
        print(f"  COMPLETE  —  Total uploads: {total}")
        print(f"{'=' * 58}")

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback; traceback.print_exc()

    finally:
        input("\nPress ENTER to close browser ...")
        driver.quit()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--file",     help="Path to file to upload")
    p.add_argument("--username", help="Enrollment number")
    p.add_argument("--password", help="Password")
    p.add_argument("--headless", action="store_true")
    args = p.parse_args()

    if args.file:     CONFIG["file"]     = args.file
    if args.username: CONFIG["username"] = args.username
    if args.password: CONFIG["password"] = args.password
    if args.headless: CONFIG["headless"] = True

    run(CONFIG)