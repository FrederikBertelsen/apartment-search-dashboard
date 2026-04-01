from datetime import datetime
import re


from dotenv import dotenv_values
from pathlib import Path

from web_automator import BrowserWrapper, PageWrapper, DataCollector

from clean_s_dk_data import clean_s_dk_data

ENV_VALUES = dotenv_values(".env")


def accept_cookies_if_needed(page: PageWrapper):
    accept_cookies_selector = ".cc-accept"
    if page.is_visible(accept_cookies_selector):
        if not page.click(accept_cookies_selector):
            print("Failed to click accept cookies button")
            exit(1)
        print("Accepted cookies")
        page.wait_for_idle()
    else:
        print("No cookie banner found, skipping")

def main():
    s_dk_username = ENV_VALUES.get("S_DK_USERNAME")
    s_dk_password = ENV_VALUES.get("S_DK_PASSWORD")

    if not s_dk_username or not s_dk_password:
        print("S_DK_USERNAME and S_DK_PASSWORD must be set in .env file")
        exit(1)

    dc = DataCollector(print_on_flush=True, print_columns=["building_name", "address"])

    with BrowserWrapper().start_browser(headless=True, humanize=False) as browser:
        page = browser.new_page()

        page.goto("https://mit.s.dk/studiebolig/login/")

        accept_cookies_if_needed(page)

        if not page.login(
                login_url="https://mit.s.dk/studiebolig/login/",

                username_selector="#id_username",
                password_selector="#id_password",
                submit_selector="#id_login",

                username=s_dk_username,
                password=s_dk_password,

                post_login_url="https://mit.s.dk/studiebolig/home/",
                success_selector="a[href='/studiebolig/logout/']",
                success_url_contains="/studiebolig/home/",

                cookies_file="cookies/s_dk_cookies.json"
                ):
            print("Failed to log in")
            exit(1)

        accept_cookies_if_needed(page)

        page.click("div[role='tablist']")
        page.wait_for_selector("div.list-group > a")
        page_urls = page.get_attributes("div.list-group > a", "href")

        if not page_urls:
            print("Failed to get building URLs")
            exit(1)

        for url in page_urls:
            print(f"Handling building: '{page.title()}'")
            page.goto(f"https://mit.s.dk{url}")

            page.sleep(10000)

            dc.set_field("url", page.get_url())

            building_name = page.title().replace("student tenancies | Apply on s.dk", "").strip()
            dc.set_field("building_name", building_name)

            dc.set_current_row_as_base()

            if not page.is_visible('table.tenancies-table > tbody > tr'):
                try:
                    page.locator('a[data-parent="#buildingGroups"]').first.click(timeout=1000*120)
                    page.wait_for_idle()
                except Exception as e:
                    print(f"    - Failed to click 'Tenancies' group for '{page.title()}'")
                    exit(1)

            page.wait_for_selector("table.tenancies-table > tbody > tr")

            tenancies_info = page.inner_text("a[href='#collapse-1'] span.text-muted")
            price_low = "N/A"
            price_high = "N/A"
            area_low = "N/A"
            area_high = "N/A"
            if tenancies_info:
                price_match = re.search(r"\d+-\d+(?= kr\.)", tenancies_info)
                area_match = re.search(r"\d+-\d+(?= m2)", tenancies_info)
                if price_match:
                    price_low, price_high = price_match.group().split("-")
                if area_match:
                    area_low, area_high = area_match.group().split("-")

            def estimate_price(area):
                if area_low == "N/A" or area_high == "N/A" or price_low == "N/A" or price_high == "N/A":
                    return "N/A"
                area_low_val = float(area_low)
                area_high_val = float(area_high)
                price_low_val = float(price_low)
                price_high_val = float(price_high)
                if area <= area_low_val:
                    return price_low_val
                elif area >= area_high_val:
                    return price_high_val
                else:
                    linear_interpolation = price_low_val + (price_high_val - price_low_val) * (area - area_low_val) / (area_high_val - area_low_val)
                    return round(linear_interpolation, 2)

            rank_to_place = {
                "A": "1-10",
                "B": "11-40",
                "C": "41-100",
                "D": "101-200",
                "E": "201-400",
                "F": "401-1000",
                "G": "1000+",
            }

            applied_tenancies = page.locator("table.tenancies-table > tbody > tr", has_text="Delete application")

            if applied_tenancies.count() == 0:
                print("No applied tenancies found, going to next building")
                continue

            print(f"Found {applied_tenancies.count()} applied tenancies.")

            for tenancy in applied_tenancies.all():
                address = tenancy.locator("td").nth(0).inner_text()            
                area = tenancy.locator("td").nth(1).inner_text()
                ranking = tenancy.locator("td").nth(2).inner_text().strip()[0]

                ranking_place = rank_to_place.get(ranking, "Unknown")

                area_value = float(area.replace("m2", "").strip())
                estimated_price = estimate_price(area_value)

                dc.set_fields({
                    "address": address,
                    "area_m2": area_value,
                    "ranking": ranking,
                    "place_in_queue": ranking_place,
                    "estimated_price_kr": estimated_price
                })
                dc.commit_row()


            # print(f"deleted_count: {deleted_count}")
            # exit()
        
    today_date_time = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    csv_path = f"data/s_dk_tenancies_{today_date_time}.csv"
    
    print(f"Saving data to '{csv_path}'")
    dc.save_csv(csv_path)

    clean_s_dk_data(csv_path)


if __name__ == "__main__":
    main()