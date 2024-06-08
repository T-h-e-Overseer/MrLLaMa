import asyncio
import logging
from bs4 import BeautifulSoup
from dataclasses import dataclass
from urllib.parse import urlparse
import re
import aiohttp

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

    async def fetch_web_page(self, url, timeout=30):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        soup = BeautifulSoup(html_content, 'html.parser')
                        return soup
                    else:
                        logger.error("Failed to fetch web page, HTTP status: %s", response.status)
                        return None
            except Exception as e:
                logger.error("Error during web page fetch: %s", str(e))
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
