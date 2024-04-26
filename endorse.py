
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
import random
import os
os.system("cls") #clear screen from previous sessions
import time
import sqlite3
from datetime import datetime, timedelta
import json # for cookies

from enum import Enum # that one is for You, my dear reader, code readability from NAKIGOE.ORG
class Status(Enum):
    SUCCESS = 0
    FAILURE = 1
    
COOKIES_PATH = 'auth/cookies.json'
LOCAL_STORAGE_PATH = 'auth/local_storage.json'
USER_AGENT = "My Standard Browser and My Standard Device" # Replace with your desired user-agent string. You can find your current browser's user-agent by searching "What's my user-agent?" in a search engine
options = webdriver.EdgeOptions()
options.use_chromium = True
options.add_argument("start-maximized")
options.page_load_strategy = 'eager' #do not wait for images to load
options.add_argument(f"user-agent={USER_AGENT}")
options.add_experimental_option("detach", True)

s = 20 #time to wait for a single component on the page to appear, in seconds; increase it if you get server-side errors «try again later»

driver = webdriver.Edge(options=options)
action = ActionChains(driver)
wait = WebDriverWait(driver,s)

def custom_wait(driver, timeout, condition_type, locator_tuple):
    wait = WebDriverWait(driver, timeout)
    return wait.until(condition_type(locator_tuple))

USERNAME = "***@gmail.com"
PASSWORD = "****"
LOGIN_PAGE = "https://www.linkedin.com/login"
CONNECTIONS_PAGE = "https://www.linkedin.com/mynetwork/invite-connect/connections/"
ENDORSE_PERIOD = 90  # pause for endorsed users in days, that is, do not open users endorsed recently
ENDORSE_ALL = False # True burns the weekly search limit. Set to True to load ALL connections (but endorse only those whose date > ENDORSED_PERIOD)

def load_data_from_json(path): return json.load(open(path, 'r'))
def save_data_to_json(data, path): os.makedirs(os.path.dirname(path), exist_ok=True); json.dump(data, open(path, 'w'))

def add_cookies(cookies): [driver.add_cookie(cookie) for cookie in cookies]
def add_local_storage(local_storage): [driver.execute_script(f"window.localStorage.setItem('{k}', '{v}');") for k, v in local_storage.items()]

def get_first_folder(path): return os.path.normpath(path).split(os.sep)[0] # for this to work, keep the cookies and localstorage in the same folder!

def delete_folder(folder_path):
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            delete_folder(file_path) if os.path.isdir(file_path) else os.remove(file_path)
        os.rmdir(folder_path)

def success():
    try:
        custom_wait(driver, 15, EC.presence_of_element_located, (By.XPATH, '//div[contains(@class,"global-nav__me")]'))
        return True
    except:
        return False

def navigate_and_check(probe_page):
    driver.get(probe_page)
    time.sleep(15)
    if success(): # return True if you are loggged in successfully independent of saving new cookies
        save_data_to_json(driver.get_cookies(), COOKIES_PATH)
        save_data_to_json({key: driver.execute_script(f"return window.localStorage.getItem('{key}');") for key in driver.execute_script("return Object.keys(window.localStorage);")}, LOCAL_STORAGE_PATH)
        return True
    else: 
        return False
   
def login():
    wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@id="username"]'))).send_keys(USERNAME)
    wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@id="password"]'))).send_keys(PASSWORD)
    action.click(wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Sign in")]')))).perform()
    time.sleep(15)
    
def check_cookies_and_login():
    driver.get(LOGIN_PAGE) # you have to open some page first before trying to load cookies!
    time.sleep(3)
    
    if os.path.exists(COOKIES_PATH) and os.path.exists(LOCAL_STORAGE_PATH):
        add_cookies(load_data_from_json(COOKIES_PATH))
        add_local_storage(load_data_from_json(LOCAL_STORAGE_PATH))
        
        if navigate_and_check(CONNECTIONS_PAGE):
            return # it is OK, you are logged in
        else: # cookies outdated, delete them
            delete_folder(get_first_folder(COOKIES_PATH)) # please keep the cookies.json and local_storage.json in the same folder to clear them successfully (or delete the outdated session files manually)
    
    driver.get(LOGIN_PAGE)
    time.sleep(3)
    login()
    navigate_and_check(CONNECTIONS_PAGE)

def scroll_to_bottom(delay=2):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        time.sleep(delay)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if last_height == new_height:
            break
        last_height = new_height

# Create table to store URLs of LinkedIn user pages and dates of Endorsing their skills
def create_table():
    conn = sqlite3.connect('users-and-dates.db')
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS endorsed_users (
        linkedin_page_url TEXT PRIMARY KEY,
        date_endorsed TEXT
    )
    """)
    conn.commit()
    conn.close()
create_table()

def check_and_endorse(driver, user_skills_url):
    linkedin_page_url = user_skills_url
    conn = sqlite3.connect('users-and-dates.db')
    cursor = conn.cursor()

    # Query for the user by linkedin_page_url
    cursor.execute("SELECT date_endorsed FROM endorsed_users WHERE linkedin_page_url = ?", (linkedin_page_url,))
    result = cursor.fetchone()

    if result:
        date_endorsed_str = result[0]
        if date_endorsed_str:
            date_endorsed = datetime.strptime(date_endorsed_str, '%Y-%m-%d')
            if datetime.now() - date_endorsed > timedelta(days=ENDORSE_PERIOD):
                if endorse_skills(driver, user_skills_url) == Status.SUCCESS: # if there are no more skills to Endorse
                    update_date_endorsed(linkedin_page_url)
        else:
            if endorse_skills(driver, user_skills_url) == Status.SUCCESS: # if there are no more skills to Endorse
                update_date_endorsed(linkedin_page_url)
    else:
        if endorse_skills(driver, user_skills_url) == Status.SUCCESS: # if there are no more skills to Endorse
            insert_user(linkedin_page_url)

    conn.close()

def insert_user(linkedin_page_url):
    conn = sqlite3.connect('users-and-dates.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO endorsed_users (linkedin_page_url, date_endorsed) VALUES (?, ?)", (linkedin_page_url, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

def update_date_endorsed(linkedin_page_url):
    conn = sqlite3.connect('users-and-dates.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE endorsed_users SET date_endorsed = ? WHERE linkedin_page_url = ?", (datetime.now().strftime('%Y-%m-%d'), linkedin_page_url))
    conn.commit()
    conn.close()

def show_more_skills():
        try:
            scroll_to_bottom()
            expand_more = custom_wait(driver, 15, EC.element_to_be_clickable, (By.XPATH, '//span[contains(., "Show more results")]/parent::button'))
            click_and_wait(expand_more,0)
            scroll_to_bottom()
            return Status.SUCCESS
        except:
            return Status.FAILURE
            
def scroll_and_focus():
    scroll_to_bottom()
        
    try:
        endorse_button = custom_wait(driver, 15, EC.element_to_be_clickable, (By.XPATH, '//span[(contains(., "Endorsed"))=false and (contains(., "endorsement"))=false and contains(., "Endorse")]/parent::button'))
        action.move_to_element(endorse_button).perform()
        return Status.SUCCESS
    
    except:
        return show_more_skills()

def eternal_wait(driver, timeout, condition_type, locator_tuple): # timeout is symbolic here since it is eternal loop
    while True:
        try:
            element = custom_wait(driver, timeout, condition_type, locator_tuple)
            return element
        except:
            print(f"\n\nWaiting for the element(s) {locator_tuple} to become {condition_type}…")
            time.sleep(1) # just to display a message
            continue

def js_click(driver, element): # 1 event
    try:
        # Scroll the element into view and dispatch a click event using JavaScript
        driver.execute_script("""
            arguments[0].scrollIntoView();
            var event = new MouseEvent('click', {
                bubbles: true,
                cancelable: true,
                view: window
            });
            arguments[0].dispatchEvent(event);
        """, element)
    except Exception as e:
        print(f"An error occurred: {e}")

def god_click(driver, element): # 3 events
    try:
        if element.is_displayed() and element.is_enabled():
            element_id = element.get_attribute("id")
            
            driver.execute_script(f"""
                arguments[0].scrollIntoView();
                var element = document.getElementById('{element_id}');
                ['mousedown', 'mouseup', 'click'].forEach(function(evtType) {{
                    var event = new MouseEvent(evtType, {{
                        'view': window,
                        'bubbles': true,
                        'cancelable': true
                    }});
                    element.dispatchEvent(event);
                }});
            """, element)
        else:
            print("Element is not visible or not enabled for clicking.")
    except Exception as e:
        print(f"An error occurred: {e}")
        
def ultimate_click(driver, element): # JS and Selenium click
    try:
        if element.is_displayed() and element.is_enabled():
            driver.execute_script(f"""
                arguments[0].scrollIntoView();
                var event = new MouseEvent('click', {{
                    'view': window,
                    'bubbles': true,
                    'cancelable': true
                }});
                arguments[0].dispatchEvent(event);
            """, element)
            action.click(element).perform()
        else:
            print("Element is not visible or not enabled for clicking.")
    except Exception as e:
        print(f"An error occurred: {e}")

def eternal_wait_for_text_to_change(element, target_text):
    print(f'Waiting for the button with an id={element.get_attribute("id")} text to change into "Endorsed"')
    last_click_time = 0  # To keep track of when the last click occurred
    while True:
        # reload the element to avoid reading from cache:
        element = custom_wait(driver, 10, EC.element_to_be_clickable, (By.ID, element.get_attribute("id")))
        current_text = element.text.strip()
        last_click_time = 0  # To keep track of when the last click occurred
        if current_text == target_text:
            return Status.SUCCESS
        
        # Click the element again if 1 second has passed since the last click (in case of connection or server fault)
        current_time = time.time()
        if current_time - last_click_time >= 3:
            ultimate_click(driver, element)
            last_click_time = current_time  # Update the last click time
            
        time.sleep(0.1)  # Adjust the sleep interval as needed, the period after which to check the button text again
          
def hide_header():
    hide_header = wait.until(EC.presence_of_element_located((By.XPATH, '//header[@id="global-nav"]')))
    driver.execute_script("arguments[0].style.display = 'none';", hide_header)
    
    hide_header_section = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="profile-content"]/div/div[2]/section')))
    driver.execute_script("arguments[0].style.display = 'none';", hide_header_section)
    
    hide_messaging = wait.until(EC.presence_of_element_located((By.XPATH, '//aside[@id="msg-overlay"]')))
    driver.execute_script("arguments[0].style.display = 'none';", hide_messaging)
    
def endorse_skills(driver, page_link):
    driver.get(page_link) 
    time.sleep(15)
    scroll_to_bottom() # ensures the page has loaded
    show_more_skills() # works better if already at bottom, shows all skills
    hide_header()
    while True:
        processed_items = set()   
        glitchy_buttons = set()
        while len(processed_items) <= 51: # eternal loop to get all the clicks to the server and bypass anti-bot buttons behaviour (return to the "Endorse" state). The cycle stops only if there are REALLY no more unendorsed buttons, the key stopper is scroll_and_focus()
            try:
                # Get all buttons that could be clicked
                endorsable_buttons = custom_wait(driver, 30, EC.presence_of_all_elements_located, (By.XPATH, '//span[(contains(., "Endorsed"))=false and (contains(., "endorsement"))=false and contains(., "Endorse")]/parent::button'))
                
                # Remove buttons already clicked
                # endorsable_buttons = [btn for btn in endorsable_buttons if btn.id not in processed_items]
                
                # endorse_button = endorsable_buttons[0]
                
                # endorse_button = custom_wait(driver, 30, EC.element_to_be_clickable, (By.XPATH, '//span[(contains(., "Endorsed"))=false and (contains(., "endorsement"))=false and contains(., "Endorse")]/parent::button')) # this element is critical, so the wait time is set to 30 seconds for testing purposes
                
                # if endorse_button.id in processed_items: 
                #     glitchy_buttons.add(endorse_button.id)
                    
                # click_and_wait(endorse_button, random.uniform(0.1, 0.25)) # increase the random time (in seconds) between pressing the "Engorse" buttons if necessary
                
                for endorse_button in endorsable_buttons:
                    if endorse_button.id in processed_items: glitchy_buttons.add(endorse_button.id); continue
                    god_click(driver, endorse_button) # anti-bot measures are a killer, use your creativity here
                    
                    # Wait for the button text to change to "Endorsed"
                    # eternal_wait_for_text_to_change(endorse_button, "Endorsed")
                    
                    time.sleep(random.uniform(0.1, 0.25)) # give time for the click to get to the server
                    
                    processed_items.add(endorse_button.id)
            
            except: # all the visible buttons have been clicked, now it is time to check and to dig in for the hidden buttons:           
                try:
                    endorsed_indicator = custom_wait(driver, 5, EC.presence_of_element_located, (By.XPATH, '//span[(contains(., "Endorsed"))]'))
                except:
                    if len(processed_items) == 0: 
                        if len(glitchy_buttons) == 0:
                            return Status.SUCCESS # exit right now if there are no skills at all indicated in the profile and save the URL in the calling function!
                        else:
                            break # try once more to click the glitchy buttons, resets the buttons storage
                
                if scroll_and_focus() == Status.FAILURE: 
                    if len(glitchy_buttons) == 0:
                        return Status.SUCCESS # no more unclicked buttons, exit and save URL in the calling function
                    else:
                        break  # try once more to click the glitchy buttons, resets the buttons storage
        
        if len(glitchy_buttons) == 0: break
        
    return Status.SUCCESS
        
def click_and_wait(element, delay=1):
    action.move_to_element(element).click().perform()
    time.sleep(delay)

def check_user(user_skills_url): 
    linkedin_page_url = user_skills_url
    conn = sqlite3.connect('users-and-dates.db')
    cursor = conn.cursor()

    # Query for the user by linkedin_page_url
    cursor.execute("SELECT date_endorsed FROM endorsed_users WHERE linkedin_page_url = ?", (linkedin_page_url,))
    result = cursor.fetchone()

    if result:
        date_endorsed_str = result[0]
        if date_endorsed_str:
            date_endorsed = datetime.strptime(date_endorsed_str, '%Y-%m-%d')
            if datetime.now() - date_endorsed < timedelta(days=ENDORSE_PERIOD):
                conn.close()
                return Status.FAILURE # that is, stop checking for other users in the contacts page at this user and start endorsing everyone in the Page_links list
        else:
            conn.close()
            return Status.SUCCESS # continue loading more users for further endorsement into the Page_links
    else:
        conn.close()
        return Status.SUCCESS # continue loading more users for further endorsement into the Page_links

def harvest_and_sift_new_candidates(list_to_endorse):
    #get first canditates displayed:
    candidates = custom_wait(driver, 15, EC.presence_of_all_elements_located, (By.XPATH, '//a[@class="ember-view mn-connection-card__link"]'))
    
    #sift the links to open against the 'Already_endorsed' list
    for person in candidates:
        user_link = person.get_attribute('href')
        skills_link = user_link + "details/skills/"
        
        if not ENDORSE_ALL: # that is, check only the most recent users in the block below and exit if found the first already endorsed user on the contacts page (they are listed on LinkedIn in the chronological order):
            if check_user(skills_link) == Status.FAILURE: return Status.FAILURE
        
        # append the link to the unendorsed list
        list_to_endorse.append(skills_link)
    
    return Status.SUCCESS # all stored successfully and there will be probably more candiatates after the scroll

def main():
    check_cookies_and_login()
    
    Page_links = [] #initial list for further endorsement
    reached_page_end = False
    last_height = driver.execute_script("return document.body.scrollHeight")

    #expand the contacts list up to the recently endorsed (there is a limit of profiles to view per week, so you want to AVOID displaying all 30000 connections):
    while not reached_page_end and not harvest_and_sift_new_candidates(Page_links) == Status.FAILURE:
        driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if last_height == new_height:
            try:
                show_more_people = wait.until(EC.element_to_be_clickable((By.XPATH, '//span[contains(., "Show more results")]/parent::button')))
                action.move_to_element(show_more_people).perform()
                action.click(show_more_people).perform()
                time.sleep(5)
            except:
                reached_page_end = True
                break
        else:
            last_height = new_height
    
    Page_links.reverse() # Since Your contacts on LinkedIn are sorted by recency, start from the bottom of the unendorsed contacts to endorse in chronological order. Important, if You want to use ENDORSE_ALL = False in the settings and to avoid loading thousands of contacts with ENDORSE_ALL = True (burns your weekly limit of contacts to search).
    
    for page_link in Page_links:
        check_and_endorse(driver, page_link)
        
    # this is for debug, to check endorsements of a single page. Wait times are usually the main culprit:
    # page_link = "https://www.linkedin.com/in/noorzaman/details/skills/"
    # check_and_endorse(driver, page_link)

    os.system("cls") #clear screen from unnecessary logs since the operation has completed successfully
    print("All Your connections are endorsed! \n \nSincerely Yours, \nNAKIGOE.ORG\n")
    driver.close()
    driver.quit()
main()
