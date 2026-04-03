from datetime import datetime
import re

from dotenv import dotenv_values
from pathlib import Path
from web_automator import BrowserWrapper, PageWrapper, DataCollector

from clean_kab_data import clean_kab_data

ENV_VALUES = dotenv_values(".env")



def accept_cookies_if_needed(page: PageWrapper):
    page.sleep_random(1000, 2000)
    accept_cookies_selector = ".cc-accept"
    if page.exists(accept_cookies_selector):
        if not page.click(accept_cookies_selector):
            print("Failed to click accept cookies button")
            exit(1)
        print("Accepted cookies")
        page.sleep_random(1000, 2000)
    else:
        print("No cookie banner found, skipping")

def main():
    kab_username = ENV_VALUES.get("KAB_USERNAME")
    kab_password = ENV_VALUES.get("KAB_PASSWORD")
    
    if not kab_username or not kab_password:
        print("KAB_USERNAME and KAB_PASSWORD must be set in .env file")
        exit(1)

    dc = DataCollector(print_on_flush=True, print_columns=["place_in_queue","company","department"])

    with BrowserWrapper().start_browser(headless=True, humanize=False) as browser:
        page = browser.new_page()

        if not page.login(
            login_url="https://www.kab-selvbetjening.dk/Portal/Log-paa",
            username_selector="#UserName", 
            password_selector="#Password",
            submit_selector="#logonButtonSubmit",
            username=kab_username,
            password=kab_password,
            success_selector="#brugerButton",
            success_url_contains="Min-side",
            post_login_url="https://www.kab-selvbetjening.dk/Ansoger/Min-side",
            # cookies_file="cookies/kab_cookies.json"
        ):

            print("Failed to login")
            exit(1)

        page.goto("https://www.kab-selvbetjening.dk/Ansoger/Min-side/Boligoensker")
        page.wait_for_idle()
        page.sleep(10000)

        building_rows = page.locator("tr[data-lejemaalgruppe-id]").all()
        print(f"Found {len(building_rows)} applied buildings")

        for building_row in building_rows:
            place_in_queue = building_row.locator("td").nth(1).inner_text()
            company_text = building_row.locator("td").nth(2).inner_text()
            type_and_address = building_row.locator("td").nth(3).inner_text()
            rent_interval = building_row.locator("td").nth(4).inner_text()
            area_interval = building_row.locator("td").nth(5).inner_text()
            floor_interval = building_row.locator("td").nth(6).inner_text()
            wait_time_interval = building_row.locator("td").nth(7).inner_text()
            tenancy_count_text = building_row.locator("td").nth(8).inner_text()
            building_url = building_row.locator("td").nth(9).locator("a").get_attribute("data-action-url")

            room_count = re.search(r"^\d+(?= rum)", type_and_address)
            if room_count:
                room_count = int(room_count.group(0))
            else:
                room_count = None
            
            address_parts = type_and_address.split("\n")
            skip_substrings = ["familieboliger", "ungdomsboliger", "lejlighedstype", " rums ", "afdeling"]
            addresses = []
            for part in address_parts:
                part = part.strip()
                if not part or part == "" or any(skip_substring.lower() in part.lower() for skip_substring in skip_substrings):
                    continue
                addresses.append(part)

            tenancy_count = re.search(r"\d+", tenancy_count_text)
            if tenancy_count:
                tenancy_count = int(tenancy_count.group(0))
            else:
                tenancy_count = None

            location = re.search(r"Område: (.*)", company_text)
            if location:
                location = location.group(1).strip()
            else:
                location = None
            
            company = company_text.strip().split('\n')[0] if company_text else None

            department = re.search(r"Afd: (.*)", company_text)
            if department:
                department = department.group(1).replace("Afd: ", "").strip()
            else:
                department = None


            dc.set_fields({
                "place_in_queue": place_in_queue,
                "company": company,
                "type_and_address": type_and_address,
                "rent_interval": rent_interval,
                "area_interval": area_interval,
                "floor_interval": floor_interval,
                "wait_time_interval": wait_time_interval,
                "tenancy_count": tenancy_count,
                "building_url": building_url,
                "room_count": room_count,
                "addresses": "|".join(addresses),
                "location": location,
                "department": department
            })
            dc.commit_row()

    today_date_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = f"data/kab_tenancies_{today_date_time}.csv"

    print(f"Saving data to '{csv_path}'")
    dc.save_csv(csv_path)

    clean_kab_data(csv_path)


if __name__ == "__main__":
    main()