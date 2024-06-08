import asyncio
import shlex
import aiohttp
import json
import os
import base64
from setup_logging import setup_logging
import logging

class Configurable:
    def __init__(self, **kwargs):
        self.models = {
            'Llama3-70B-Instruct': {'model_executable': '/mnt/ntfs/llamafiles/Meta-Llama-3-70B-Instruct.Q4_0.llamafile', 'n-gpu-layers': 999, 'nobrowser': True, 'port': 8000, 'timeout': 300, 'ctx-size': 5000},
            'llava-v1.5-7b': {'model_executable': '/mnt/ntfs/llamafiles/llava-v1.5-7b-q4.llamafile', 'n-gpu-layers': 10, 'nobrowser': True, 'port': 8001, 'timeout': 300, 'ctx-size': 2048}
        }

        model_name = kwargs.pop('model_name', 'Llama3-70B-Instruct')
        self.initialize_model_config(model_name=model_name, **kwargs)

    def initialize_model_config(self, model_name, **kwargs):
        if model_name not in self.models:
            raise ValueError(f"Model '{model_name}' is not recognized. Available models are: {list(self.models.keys())}")

        self.config = self.models[model_name].copy()

        for key, value in kwargs.items():
            self.config[key] = value

        for key, value in self.config.items():
            setattr(self, key, value)

    def format_settings(self, separator=', '):
        settings = {key: getattr(self, key) for key in self.config}
        return separator.join(f'{key}: {value}' for key, value in settings.items())

    def get_settings(self):
        return {key: getattr(self, key) for key in self.config}

    def update_setting(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
            self.config[key] = value

    def apply_defaults(self):
        for key in list(self.config):
            if key not in self.models[self.config['model_name']]:
                delattr(self, key)
                del self.config[key]
        self.initialize_model_config(model_name=self.config['model_name'])

class LlamaAPI:
    def __init__(self, **kwargs):
        self.logger = setup_logging("development", 'discord.LlamaAPI')
        self.logger.debug("Initializing LlamaAPI")
        self.process = None
        self.is_running = False
        self.in_startup = False
        self.api_ready = asyncio.Event()
        self.api_startup = asyncio.Event()
        self.configurable = Configurable(**kwargs)
        self.history = []
        self.base_url = ""

    async def start_api(self):
        if self.in_startup or self.is_running:
            self.logger.debug("API Running: %s, API in Startup: %s", self.is_running, self.in_startup)
            return
        self.in_startup = True
        self.logger.debug("Starting API process")

        cli_args = ["/bin/bash", self.configurable.model_executable]
        for key, value in self.configurable.config.items():
            if key not in ['model_executable']:
                if isinstance(value, bool) and value:
                    cli_args.append(f"--{key}")
                elif not isinstance(value, bool):
                    cli_args.append(f"--{key}")
                    cli_args.append(str(value))

        cli_command_string = " ".join(shlex.quote(arg) for arg in cli_args)
        self.logger.debug(f"Command to run: {cli_command_string}")

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cli_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy()
            )
            if self.process:
                self.api_startup.set()
                asyncio.create_task(self.monitor_api())
        except Exception as e:
            self.logger.error(f"Failed to start the API process: {e}")
            self.in_startup = False

    async def send_request(self, context, prompt, image_files=[], history=None):
        await self.api_ready.wait()
        prompt_text = self.construct_prompt(context, prompt, history)
        payload = self.construct_payload(prompt_text, image_files)
        self.logger.debug(f"Constructed payload: {json.dumps(payload, indent=2)}")

        headers = {'Accept': 'text/event-stream', 'Content-Type': 'application/json'}
        url = f"{self.base_url}/completion"
        self.logger.debug(f"Sending request to {url}")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    self.logger.error(f"Failed to get valid response, HTTP status: {response.status}")
                    return None
                if response.headers.get('Content-Type') != 'text/event-stream':
                    self.logger.error(f"Unexpected Content-Type: {response.headers.get('Content-Type')}")
                    return None
                complete_response = await self.read_response(response)
                self.logger.info(f"Complete response received: {complete_response}")
                return complete_response

    def construct_prompt(self, context, prompt, history):
        if history:
            history_text = "\n".join(f"{item['role']}: {item['content']}" for item in history)
            prompt_text = f"{history_text}\n{context}\n{prompt}" if context else f"{history_text}\n{prompt}"
            return prompt_text
        else:
            return f"{context}\n{prompt}" if context else prompt

    def construct_payload(self, prompt_text, image_files):
        payload = {
            "stream": True,
            "n_predict": 400,
            "temperature": 0.7,
            "repeat_last_n": 256,
            "repeat_penalty": 1.18,
            "top_k": 40,
            "top_p": 0.95,
            "min_p": 0.05,
            "tfs_z": 1,
            "typical_p": 1,
            "presence_penalty": 0,
            "frequency_penalty": 0,
            "mirostat": 0,
            "mirostat_tau": 5,
            "mirostat_eta": 0.1,
            "grammar": "",
            "n_probs": 0,
            "min_keep": 0,
            "image_data": [],
            "cache_prompt": True,
            "api_key": "",
            "slot_id": -1,
            "stop": ["</s>", "Llama:", "User:"],
            "prompt": prompt_text
        }
        if image_files:
            base64_encoded = base64.b64encode(image_files[0]).decode('utf-8')
            payload["image_data"] = [{'data': base64_encoded, 'id': 10}]
        return payload

    async def read_response(self, response):
        complete_response = ""
        try:
            async for line in response.content:
                if line.startswith(b'data:'):
                    content_line = line.strip()[6:]
                    try:
                        data = json.loads(content_line.decode('utf-8'))
                        self.logger.debug(f"Stream data received: {data}")
                        if 'content' in data and data['content']:
                            complete_response += data['content']
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON decoding error: {e}, content: {content_line.decode('utf-8', 'ignore')}")
        except Exception as e:
            self.logger.error(f"Error while reading response: {str(e)}")
        return complete_response

    async def monitor_api(self):
        try:
            assert self.process.stdout is not None, "Subprocess stdout is None."
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                line_decoded = line.decode().strip()
                self.logger.debug("API Output: %s", line_decoded)

                try:
                    json_output = json.loads(line_decoded)
                    self.logger.debug("Parsed JSON Output: %s", json_output)

                    if json_output.get("function") == "server_cli" and json_output.get("msg") == "HTTP server listening":
                        url = f"http://{json_output['hostname']}:{json_output['port']}"
                        self.base_url = url
                        self.logger.info(f"API is now ready and running at {url}")
                        if not self.is_running:
                            self.is_running = True
                            self.api_ready.set()
                            self.in_startup = False
                            self.api_startup.clear()

                except json.JSONDecodeError:
                    self.logger.error("Failed to decode JSON from subprocess output, ignoring: %s", line_decoded)

        except Exception as e:
            self.logger.error(f"Unexpected error monitoring API: {e}")
            await self.stop_api()

    async def stop_api(self):
        if self.process and self.is_running:
            self.logger.debug("Stopping API process")
            self.process.terminate()
            await self.process.wait()
            self.is_running = False
            self.api_ready.clear()
            self.logger.info("API process stopped")
        else:
            self.logger.debug("API process is not running")
