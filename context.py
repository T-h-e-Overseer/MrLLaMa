import subprocess
import logging
from bs4 import BeautifulSoup
from dataclasses import dataclass
from urllib.parse import urlparse
import re

logger = logging.getLogger('discord.context')

@dataclass
class URLDetails:
    full_url: str
    scheme: str
    netloc: str
    path: str
    params: str
    query: str
    fragment: str
    username: str
    password: str
    hostname: str
    port: int

class Context:
    def __init__(self):
        logger.debug("Context initialized.")

    def fetch_web_page(self, url, timeout=30):
        try:
            logger.debug(f"Attempting to fetch the web page: {url} using curl")
            curl_command = ['curl', '-L', '-s', '--max-time', str(timeout), url]
            result = subprocess.run(curl_command, capture_output=True, text=True)

            if result.returncode == 0:
                logger.debug("Successfully fetched the web page using curl")
                html_content = result.stdout
                soup = BeautifulSoup(html_content, 'html.parser')
                return soup
            else:
                logger.error(f"Failed to fetch web page using curl, return code: {result.returncode}")
                logger.error(f"Curl stderr: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("TimeoutError during web page fetch using curl")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during web page fetch using curl: {e}")
            return None

    def find_urls(self, text):
        regex = r"((([A-Za-z]{3,9}:(?:\/\/)?)(?:[-;:&=+\$,\w]+@)?[A-Za-z0-9.-]+|(?:www\.|[-;:&=+\$,\w]+@)[A-Za-z0-9.-]+)((?:\/[\+~%\/.\w\-_]*)?\??(?:[-\+=&;%@\.\w_]*)#?(?:[\w]*))?)"
        found_urls = re.findall(regex, text)
        return [self.examine_url(url[0]) for url in found_urls]

    def examine_url(self, url):
        parsed_url = urlparse(url)
        return URLDetails(
            full_url=url,
            scheme=parsed_url.scheme if parsed_url.scheme else 'http',
            netloc=parsed_url.netloc,
            path=parsed_url.path,
            params=parsed_url.params,
            query=parsed_url.query,
            fragment=parsed_url.fragment,
            username=parsed_url.username,
            password=parsed_url.password,
            hostname=parsed_url.hostname,
            port=parsed_url.port
        )

# Example usage of the Context class for testing purposes
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    context = Context()
    url = "http://cnn.com"
    soup = context.fetch_web_page(url, timeout=30)

    if soup:
        logger.info("Successfully fetched the web page!")
        # Print the title of the page as an example
        logger.info(soup.title.string if soup.title else "No title found")
    else:
        logger.error("Failed to fetch the web page.")
