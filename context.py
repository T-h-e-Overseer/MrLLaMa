import subprocess
import logging
import asyncio
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
        self.message_queue = asyncio.Queue()
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self.monitor_message_processing())
        self.llama_api_url = "http://localhost:8010"
        self.context = "You are a helper AI that helps process URL analysis of web pages. Please follow all instructions and give concise responses."

    async def fetch_web_page(self, url, timeout=30):
        try:
            logger.debug(f"Attempting to fetch the web page: {url} using curl")
            curl_command = ['curl', '-L', '-s', '--max-time', str(timeout), url]
            result = await asyncio.create_subprocess_exec(*curl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            stdout, stderr = await result.communicate()
            if result.returncode == 0:
                logger.debug("Successfully fetched the web page using curl")
                html_content = stdout.decode()
                soup = BeautifulSoup(html_content, 'html.parser')
                return soup
            else:
                logger.error(f"Failed to fetch web page using curl, return code: {result.returncode}")
                logger.error(f"Curl stderr: {stderr.decode()}")
                return None
        except asyncio.TimeoutError:
            logger.error("TimeoutError during web page fetch using curl")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during web page fetch using curl: {e}")
            return None

    def extract_sections(self, soup):
        sections = []
        for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            sections.append(header.get_text(strip=True))
        return sections

    async def analyze_sections(self, sections):
        prompt = self.context + "\n\n"
        prompt += "Here are the sections of the web page:\n"
        for section in sections:
            prompt += f"- {section}\n"
        prompt += "Which of these seem to be the most important parts of the web page?"

        response = await self.send_request_to_llama(prompt)
        return response

    async def send_request_to_llama(self, prompt):
        try:
            logger.debug(f"Sending request to Llama API with prompt: {prompt}")
            headers = {'Content-Type': 'application/json'}
            json_data = {
                'prompt': prompt
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(self.llama_api_url, json=json_data, headers=headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get('response')
                    else:
                        logger.error(f"Failed to get response from Llama API: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error sending request to Llama API: {e}")
            return None

    async def process_messages(self):
        logger.debug("Starting message processing loop")
        try:
            while True:
                message = await self.message_queue.get()
                url = message['url']
                callback = message['callback']
                soup = await self.fetch_web_page(url)

                if soup:
                    logger.info("Successfully fetched the web page!")
                    sections = self.extract_sections(soup)
                    response = await self.analyze_sections(sections)
                    await callback(response)
                else:
                    logger.error("Failed to fetch the web page.")
                
                self.message_queue.task_done()
        except Exception as e:
            logger.error(f"Error in process_messages loop: {e}")
            logger.debug("Restarting process_messages loop")
            self.loop.create_task(self.process_messages())

    async def monitor_message_processing(self):
        while True:
            try:
                logger.debug("Starting the message processing loop")
                await self.process_messages()
            except Exception as e:
                logger.error(f"Message processing loop crashed: {e}")
                logger.debug("Clearing message queue and restarting message processing loop")
                self.message_queue = asyncio.Queue()
                await asyncio.sleep(1)  # Small delay to avoid tight loop in case of repeated failures

    async def queue_message(self, url, callback):
        message = {'url': url, 'callback': callback}
        await self.message_queue.put(message)
        logger.debug(f"Queued message for URL: {url}")

# Example usage of the Context class for testing purposes
if __name__ == "__main__":
    import aiohttp

    logging.basicConfig(level=logging.DEBUG)
    context = Context()

    async def example_callback(response):
        logger.info(f"LLM Response: {response}")

    url = "http://cnn.com"
    context.loop.run_until_complete(context.queue_message(url, example_callback))
