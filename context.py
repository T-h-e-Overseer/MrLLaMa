import logging
from bs4 import BeautifulSoup
from dataclasses import dataclass
from urllib.parse import urlparse
import re
import aiohttp
import asyncio

# Import the setup_logging function
from setup_logging import setup_logging  # Ensure this is the correct path

# Initialize the logger using setup_logging
logger = setup_logging(environment='development', logger_name='discord.context')

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

    async def fetch_web_page(self, url, timeout=30):
        try:
            logger.debug(f"Attempting to fetch the web page: {url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    logger.debug(f"Received response with status code: {response.status}")
                    if response.status == 200:
                        html_content = await response.text()
                        logger.debug("Successfully fetched HTML content")
                        soup = BeautifulSoup(html_content, 'html.parser')
                        return soup
                    else:
                        logger.error(f"Failed to fetch web page, status code: {response.status}")
                        return None
        except aiohttp.ClientError as e:
            logger.error(f"ClientError during web page fetch: {e}")
            return None
        except asyncio.TimeoutError:
            logger.error("TimeoutError during web page fetch")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during web page fetch: {e}")
            return None

    def find_urls(self, text):
        logger.debug(f"Attempting to find URLs in text: {text}")
        regex = r"((([A-Za-z]{3,9}:(?:\/\/)?)(?:[-;:&=+\$,\w]+@)?[A-Za-z0-9.-]+|(?:www\.|[-;:&=+\$,\w]+@)[A-Za-z0-9.-]+)((?:\/[\+~%\/.\w\-_]*)?\??(?:[-\+=&;%@\.\w_]*)#?(?:[\w]*))?)"
        found_urls = re.findall(regex, text)
        logger.debug(f"Found URLs: {found_urls}")
        url_details_list = [self.examine_url(url[0]) for url in found_urls]
        logger.debug(f"Parsed URL details: {url_details_list}")
        return url_details_list

    def examine_url(self, url):
        logger.debug(f"Examining URL: {url}")
        parsed_url = urlparse(url)
        url_details = URLDetails(
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
        logger.debug(f"URL details: {url_details}")
        return url_details

    async def fetch_justpasteit_content(self, url):
        logger.debug(f"Fetching justpasteit content from URL: {url}")
        soup = await self.fetch_web_page(url)
        if soup:
            logger.debug("Successfully fetched web page content, parsing...")
            article_content = soup.find('div', id='articleContent')
            if article_content:
                content = article_content.get_text(strip=True)
                logger.debug(f"Found article content: {content}")
                return content
            else:
                logger.debug("Article content not found.")
        else:
            logger.debug("Failed to fetch web page content.")
        return None
