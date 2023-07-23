from datetime import datetime
from typing import Iterator, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from lxml import etree


class FacebookScraper:
    """
    Very unstable version of facebook user posts scraper.\n
    Scrapes images from a Facebook profile in chronological order.\n
    Does **not** guarantee to scrape all images.\n
    Usage:\n
    with FacebookScraper("username") as scraper:\
        for image_id, image_url in scraper.scraped_images():\
            print(image_id, image_url)
    Version: 0.1.0
    """

    COOKIES_POPUP_XPATH = (
        "/html/body/div[2]/div[1]/div/div[2]/div/div/div/div[2]/div/div[1]/div[2]"
    )
    LOGIN_POPUP_XPATH = "/html/body/div[1]/div/div[1]/div/div[5]/div/div/div[1]/div/div[2]/div/div/div/div[1]/div"
    POST_XPATH_TEMPLATE = "/html/body/div[1]/div/div[1]/div/div[3]/div/div/div/div[1]/div[1]/div/div/div[4]/div[2]/div/div[2]/div/div[{}]"
    IMAGE_IN_POST_XPATH = "//div/div/div/div/div/div/div/div/div/div/div[2]/div/div/div[3]/div/div[1]/a/div[1]/div/div/div/img/@src"
    IMAGE_POST_IN_POST_XPATH = "//div/div/div/div/div/div/div/div/div/div/div[2]/div/div/div[3]/div/div/a/@href"

    def __init__(self, fb_username: str):
        # geckodriver_autoinstaller.install()
        self.username = fb_username
        self.driver = None

    def __enter__(self):
        options = Options()
        options.add_argument("-headless")
        self.driver = webdriver.Firefox(options=options)
        self.driver.set_window_position(0, 0)
        self.driver.set_window_size(2560, 1440)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.driver.quit()

    def scraped_images(
        self, number_of_posts: Optional[int] = None, newer_than: datetime = None
    ) -> Iterator[Tuple[int, str]]:
        """
        Returns an iterator of users image urls in chronological order.\n
        Select number_of_posts to limit it.\n
        If number_of_posts is None, it will try to scrape first 1000 posts.
        """
        if self.driver is None:
            raise ValueError(
                "Driver is not initialized. Use the 'with' statement to run the scraper."
            )

        try:
            self.driver.get("http://facebook.com/" + self.username)

            wait = WebDriverWait(self.driver, 4, poll_frequency=1)

            cookies_popup = wait.until(
                EC.presence_of_element_located((By.XPATH, self.COOKIES_POPUP_XPATH))
            )
            cookies_popup.click()

            login_popup = wait.until(
                EC.presence_of_element_located((By.XPATH, self.LOGIN_POPUP_XPATH))
            )
            login_popup.click()

            max = 1000 if number_of_posts is None else number_of_posts
            for i in range(1, max):
                try:
                    post: WebElement = wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, self.POST_XPATH_TEMPLATE.format(i))
                        )
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView();", post)
                    outer_html = post.get_attribute("outerHTML")
                    dom = etree.HTML(str(outer_html))
                    images = dom.xpath(self.IMAGE_IN_POST_XPATH)
                    image_post_href = dom.xpath(self.IMAGE_POST_IN_POST_XPATH)

                    if len(images) == 0 or len(image_post_href) == 0:
                        continue

                    image_id = parse_qs(urlparse(image_post_href[0]).query)["fbid"][0]
                    image_url = images[0]

                    yield (int(image_id), image_url)
                except Exception as e:
                    print("Error", e)
                    # pass, that number does not work
                    continue
        finally:
            self.driver.quit()
