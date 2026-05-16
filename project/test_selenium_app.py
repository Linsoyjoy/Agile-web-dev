import unittest
import threading
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from app import create_app, db





localHost = "http://localhost:5000/"


class SeleniumTestCase(unittest.TestCase):

    def setUp(self):
        options = Options()

        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.password_manager_leak_detection": False
        }

        options.add_experimental_option("prefs", prefs)
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-save-password-bubble")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--user-data-dir=/tmp/chrome-test-profile")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-features=PasswordManager,PasswordCheck")
        options.add_argument("--disable-features=PasswordLeakDetection,PasswordManagerOnboarding,SafeBrowsingEnhancedProtection")
        self.app = create_app('config.DevelopmentConfig')
        with self.app.app_context():
             db.create_all()

        self.server_thread = threading.Thread(target=self.app.run, kwargs={'debug': False, 'use_reloader': False})
        self.server_thread.daemon = True
        self.server_thread.start()
        time.sleep(1)
        self.browser = webdriver.Chrome(options=options)

    def tearDown(self):

        self.browser.quit()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_full_website(self):
        # Method for accessing pages from dropdown menu
        def access_page(page):
            dropdown_menu = self.browser.find_element(By.CSS_SELECTOR, "a.nav-link.dropdown-toggle")
            dropdown_menu.click()
            WebDriverWait(self.browser, 10).until(
                EC.visibility_of_element_located((By.LINK_TEXT, "Profile"))
            )
            link = self.browser.find_element(By.LINK_TEXT, page)
            link.click()
            WebDriverWait(self.browser, 10).until(
                EC.title_contains(page)
            )
            self.assertIn(page, self.browser.title)
            return()

        self.browser.get(localHost)
        # Confirm landing page loaded, move to Sign up page
        self.assertIn("Chessmate", self.browser.title)
        sign_up_page = self.browser.find_element(By.LINK_TEXT, "Sign Up")
        sign_up_page.click()
        WebDriverWait(self.browser, 10).until(
            EC.title_contains("Sign Up")
        )
        # 
        username_field = self.browser.find_element(By.NAME, "username")
        email_field = self.browser.find_element(By.NAME, "email")
        password_field = self.browser.find_element(By.NAME, "password")
        confirm_password_field = self.browser.find_element(By.NAME, "confirm_password")

        username_field.send_keys("testuser")
        email_field.send_keys("testuser@example.com")
        password_field.send_keys("password123")
        confirm_password_field.send_keys("password123")

        submit_button = self.browser.find_element(By.XPATH,'//button[text()="Sign Up"]')        
        submit_button.click()

        WebDriverWait(self.browser, 10).until(
            EC.title_contains("Login")
        )

        # Attempt to log in with the new user
        self.assertIn("Login", self.browser.title)

        username_field = self.browser.find_element(By.NAME, "username")
        password_field = self.browser.find_element(By.NAME, "password")
        
        username_field.send_keys("testuser")
        password_field.send_keys("password123")
        submit_button = self.browser.find_element(By.XPATH,'//button[text()="Log in"]')        
        submit_button.click()

        WebDriverWait(self.browser, 10).until(
            EC.title_contains("Home")
        )

        self.assertIn("Home", self.browser.title)

        # Confirm access to all dropdown menu pages
        access_page("Profile")
        access_page("Friends")
        # Confirm access to stats and that correct wins, losses and draws are showing
        access_page("Stats")
        wins_element = self.browser.find_element(By.XPATH, "//h5[text()='Wins']/following-sibling::h3")
        losses_element = self.browser.find_element(By.XPATH, "//h5[text()='Losses']/following-sibling::h3")
        draws_element = self.browser.find_element(By.XPATH, "//h5[text()='Draws']/following-sibling::h3")
        self.assertEqual(wins_element.text, "0")
        self.assertEqual(losses_element.text, "0")
        self.assertEqual(draws_element.text, "0")

        access_page("Calendar")
        access_page("Leaderboard")

        # Access FAQ in footer
        faq_page = self.browser.find_element(By.LINK_TEXT, "FAQs")
        self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", faq_page)
        time.sleep(1)
        faq_page.click()
        
        # Access Query page in footer
        query_page = self.browser.find_element(By.LINK_TEXT, "Report issue")
        self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", query_page)
        time.sleep(1)
        query_page.click()

        # Return to home page
        access_page("Home")

        new_record_button = self.browser.find_element(By.LINK_TEXT, "Add new record")
        new_record_button.click()
        WebDriverWait(self.browser, 10).until(
            EC.title_contains("Add New Game Record")
        )
        self.assertIn("Add New Game Record", self.browser.title)
        match_type = self.browser.find_element(By.NAME, "match_type")
        match_type.click()
        match_type_option = WebDriverWait(self.browser, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//option[text()='Past Match (Already Played)']"))
        )
        match_type_option.click()

        opponent_field = self.browser.find_element(By.NAME, "opponent")
        result_field = self.browser.find_element(By.NAME, "result")
        colour_field = self.browser.find_element(By.NAME, "colour")
        opening_field = self.browser.find_element(By.NAME, "opening")
        termination_field = self.browser.find_element(By.NAME, "termination")
        date_field = self.browser.find_element(By.NAME, "date_played")
        game_record_field = self.browser.find_element(By.NAME, "game_record")
        opponent_field.send_keys("testopponent")
        result_field.send_keys("Win")
        colour_field.send_keys("White")
        opening_field.send_keys("Italian Game")
        termination_field.click()
        termination_option = WebDriverWait(self.browser, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//option[text()='Resignation']"))
        )        
        termination_option.click()
        date_field.send_keys("01-01-2025")
        game_record_field.send_keys("1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 Nxe4 8. O-O Bxc3 9. bxc3 d5 10. Ba3 Be6 11. Bd3 Nd6 12. Re1 Qd7 13. Ng5 O-O-O 14. Nxe6 fxe6 15. Qg4 Rde8 16. Rab1 h5 17. Qh3 g5 18. Bxd6 cxd6 19. Rb2 g4 20. Qe3 e5 21. Reb1 b6 22. Ba6+ Kb8 23. a4 exd4 24. Qd2 dxc3 25. Qxc3 d4 26. Qc4 Ne5 27. Qd5 d3 28. a5 Qc6 29. axb6 Qxd5 30. bxa7+ Kxa7 31. Ra1 Qa8")
        time.sleep(1)
        submit_button = self.browser.find_element(By.XPATH,'//button[text()="Save Record"]')
        self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
        time.sleep(1)
        submit_button.click()

        access_page("Stats")
        wins_element = self.browser.find_element(By.XPATH, "//h5[text()='Wins']/following-sibling::h3")
        losses_element = self.browser.find_element(By.XPATH, "//h5[text()='Losses']/following-sibling::h3")
        draws_element = self.browser.find_element(By.XPATH, "//h5[text()='Draws']/following-sibling::h3")
        self.assertEqual(wins_element.text, "1")
        self.assertEqual(losses_element.text, "0")
        self.assertEqual(draws_element.text, "0")


    def test_incorrect_access_attempts(self):
        self.browser.get(localHost)
        # Attempt to access protected route without logging in
        self.browser.get(localHost + "profile")
        WebDriverWait(self.browser, 10).until(
            EC.title_contains("Login")
        )
        self.assertIn("Login", self.browser.title)
        self.browser.get(localHost + "leaderboard")
        WebDriverWait(self.browser, 10).until(
            EC.title_contains("Login")
        )
        self.assertIn("Login", self.browser.title)

        sign_up_page = self.browser.find_element(By.XPATH, "//a[@href='/signup']")
        sign_up_page.click()
        WebDriverWait(self.browser, 10).until(
            EC.title_contains("Sign Up")
        )
        time.sleep(1)
        username_field = self.browser.find_element(By.NAME, "username")
        email_field = self.browser.find_element(By.NAME, "email")
        password_field = self.browser.find_element(By.NAME, "password")
        confirm_password_field = self.browser.find_element(By.NAME, "confirm_password")
        # Test sign up attempt with missing username field
        username_field.send_keys("")
        email_field.send_keys("testuser@example.com")
        password_field.send_keys("password123")
        confirm_password_field.send_keys("password123")

        submit_button = self.browser.find_element(By.XPATH,'//button[text()="Sign Up"]')        
        submit_button.click()





if __name__ == "__main__":
    unittest.main()