"""Automation tool for updating Flipkart settlement prices.

The script drives a headless Chrome instance via Selenium to update the
settlement price for SKUs listed in an Excel sheet. A brief pause is
introduced on startup so that the user can log in if required.

Run ``python flipkartpricing.py --help`` for available command line options.
"""

import os
import time
import logging
import argparse

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ────── CONFIG ──────
EXCEL_PATH        = "input.xlsx"
SELENIUM_PROFILE  = r"C:\Users\DELL\AppData\Local\Google\Chrome\SeleniumProfile"
WAIT_TIMEOUT      = 20
DELAY             = 2

LISTING_URL = (
    "https://seller.flipkart.com/index.html"
    "#dashboard/listings-management"
    "?listingState=ACTIVE&listingsSearchQuery={sku}&partnerContext=ALL"
)

# ────── Logging ──────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("price_update.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ],
)

class PriceUpdateBot:
    def __init__(self, excel_path=EXCEL_PATH, login_wait=60, headless=True):
        self.excel_path = excel_path
        os.makedirs(SELENIUM_PROFILE, exist_ok=True)

        opts = Options()
        opts.add_argument(f"--user-data-dir={SELENIUM_PROFILE}")
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--password-store=basic")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])

        # create a Service that sends logs to null
        service = Service(log_path=os.devnull)

        logging.info("Launching headless Chrome…")
        self.driver = webdriver.Chrome(service=service, options=opts)
        self.wait   = WebDriverWait(self.driver, WAIT_TIMEOUT)

        logging.info(
            f"🔑 If first run, please log in within {login_wait} seconds…"
        )
        time.sleep(login_wait)

    def _click(self, el):
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'})", el)
        ActionChains(self.driver).move_to_element(el).pause(0.2).click(el).perform()

    def _open_listing(self, sku):
        url = LISTING_URL.format(sku=sku)
        logging.info(f"→ Navigating to SKU {sku}")
        self.driver.get(url)
        time.sleep(5)

    def _open_pricing_modal(self, sku):
        row = self.wait.until(EC.presence_of_element_located((
            By.XPATH, f"//tr[.//td[contains(text(),'{sku}')]]"
        )))
        icon = row.find_element(By.XPATH, ".//div[contains(@class,'ClickableContainer')]")
        self._click(icon)
        time.sleep(DELAY)
        btn = self.wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[.//span[text()='Continue to pricing']]"
        )))
        self._click(btn)
        time.sleep(DELAY)

    def _get_settlement(self):
        inp = self.wait.until(EC.presence_of_element_located((By.ID, "settlementValue")))
        return float(inp.get_attribute("value"))

    def _set_and_apply(self, val):
        inp = self.wait.until(EC.element_to_be_clickable((By.ID, "settlementValue")))
        inp.clear()
        inp.send_keys(f"{val:.2f}")
        time.sleep(1)
        btn = self.wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(@class,'primary') and contains(.,'Apply')]"
        )))
        self._click(btn)
        time.sleep(3)

    def update_price_for(self, sku, target):
        try:
            self._open_listing(sku)
            self._open_pricing_modal(sku)

            current = self._get_settlement()
            logging.info(f"    Starting @ ₹{current:.2f}, target ₹{target:.2f}")

            while current < target:
                next_val = current * 1.0199
                if next_val > target:
                    next_val = target
                logging.info(f"    ↑ Bumping to ₹{next_val:.2f}")
                self._set_and_apply(next_val)
                current = next_val

            logging.info(f"✅ Done with {sku}")
        except Exception as e:
            logging.error(f"❌ Failed on {sku}: {e}", exc_info=True)

    def run(self):
        df = pd.read_excel(
            self.excel_path, dtype={"SKU": str, "FinalPrice": float}
        )
        for _, r in df.iterrows():
            self.update_price_for(r["SKU"].strip(), float(r["FinalPrice"]))

    def quit(self):
        logging.info("Closing Chrome…")
        self.driver.quit()

def main():
    parser = argparse.ArgumentParser(description="Update Flipkart settlement prices")
    parser.add_argument(
        "--excel",
        default=EXCEL_PATH,
        help="Path to Excel file with SKU and FinalPrice columns",
    )
    parser.add_argument(
        "--login-wait",
        type=int,
        default=60,
        help="Seconds to pause for manual login",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run Chrome with a visible window",
    )
    args = parser.parse_args()

    bot = PriceUpdateBot(
        excel_path=args.excel,
        login_wait=args.login_wait,
        headless=not args.no_headless,
    )
    try:
        bot.run()
    finally:
        bot.quit()


if __name__ == "__main__":
    main()
