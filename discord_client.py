import asyncio
import discord
from discord.ext import commands
from setup_logging import setup_logging
import bot_commands
from llama_api import LlamaAPI
from context_config import ContextConfig
from context import Context  # Ensure this import is correct based on your project structure

class DiscordClient(commands.Bot):
    def __init__(self, llama_api, prompt_prefix=':', command_prefix='!', intent_discord=None, debug_bot_commands=True, log_all_messages=True):
        # Setup logging
        self.logger = setup_logging("development", 'discord.DiscordClient')
        self.logger.debug("Initializing DiscordClient")

        # Initialize context configuration
        self.context_config = ContextConfig()
        
        # Store the LlamaAPI instance
        self.llama_api = llama_api

        # Setup intents for the Discord bot
        intents = intent_discord or discord.Intents.default()
        intents.messages = True
        intents.guilds = True
        intents.message_content = True

        # Initialize the parent class
        super().__init__(command_prefix=command_prefix, intents=intents)
        
        # Debug and logging settings
        self.debug_bot_commands = debug_bot_commands
        self.log_all_messages = log_all_messages
        
        # Initialize the multimodal API
        self.multimodal_api = LlamaAPI(model_name="llava-v1.5-7b")
        
        # Create a message queue
        self.message_queue = asyncio.Queue()
        self.prompt_prefix = prompt_prefix
        
        # Store conversation channels
        self.conversation_channels = set()
        
        # Load commands
        self.load_commands()
        
        # Initialize the Context class for URL handling
        self.context = Context()

    async def setup_hook(self):
        # Start processing messages
        self.loop.create_task(self.monitor_message_processing())

    def load_commands(self):
        # Import and add bot commands
        self.logger.debug("Loading commands")
        from bot_commands import set_config, api_state, start_simulation
        if isinstance(bot_commands.set_config, commands.Command):
            self.add_command(set_config)
            self.add_command(api_state)
            self.add_command(start_simulation)
        self.logger.debug("Commands loaded")

    async def on_ready(self):
        # Called when the bot is ready
        self.logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)

    async def on_message(self, message):
        self.logger.debug(f"Received message: {message.content} from {message.author}")
        # Detect URLs in the message content
        urls = self.context.find_urls(message.content)
        self.logger.debug(f"URLs: {urls}")
        if urls:
            for url_details in urls:
                if 'justpaste.it' in message.content:
                    self.logger.debug(f"justpaste.it URL found: {url_details.full_url}")
                    content = await self.context.fetch_justpasteit_content(url_details.full_url)
                    if content:
                        new_content = message.content.replace(url_details.full_url, content)
                        message.content = f":{new_content}"
                    else:
                        await message.channel.send("Failed to fetch content from justpaste.it.")
        else:
            self.logger.debug("No URLs found in the message content.")
        # Ignore the bot's own messages unless they are in a conversation channel
        if message.author == self.user and message.channel.id not in self.conversation_channels:
            self.logger.debug("Message is from the bot and not in a conversation channel, ignoring")
            return

        # Process command messages
        if message.content.startswith('!'):
            self.logger.debug("Message is a command, processing command")
            await self.process_commands(message)
            return

        # Process messages starting with the prompt prefix
        if message.content.startswith(self.prompt_prefix):
            self.logger.debug("Message starts with prompt prefix, processing prompt")
            prompt = message.content.strip()[len(self.prompt_prefix):].strip()
            image_files = await self.get_image_files(message)

            cleaned_prompt = [prompt, message, image_files, "prompt"]
            await self.message_queue.put(cleaned_prompt)
            await message.channel.send("Prompt received and queued for processing!")
            self.logger.debug(f"Queued prompt for processing: {cleaned_prompt}")
            return


    async def get_image_files(self, message):
        # Extract image files from the message
        self.logger.debug("Checking for image attachments in the message")
        image_files = []
        if message.attachments:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif']):
                    self.logger.debug(f"Found image attachment: {attachment.filename}")
                    image_content = await attachment.read()
                    image_files.append(image_content)
        self.logger.debug(f"Image files extracted: {len(image_files)}")
        return image_files

    async def process_messages(self):
        self.logger.debug("Starting message processing loop")
        try:
            while True:
                queued_message = await self.message_queue.get()
                message_type = queued_message[0]

                if message_type == "justpasteit":
                    url = queued_message[1]
                    message = queued_message[2]
                    content = await self.context.fetch_justpasteit_content(url)
                    if content:
                        await message.channel.send(f"Fetched content from justpaste.it:\n{content}")
                    else:
                        await message.channel.send("Failed to fetch content from justpaste.it.")
                else:
                    cleaned_prompt = queued_message[0]
                    image_files = queued_message[2]
                    message_type = queued_message[3]
                    multimodal_response = ""

                    self.logger.debug(f"Processing queued message: {queued_message}")
                    if not self.llama_api.is_running and not self.llama_api.in_startup:
                        self.logger.debug("Llama API is not running, starting API")
                        await self.llama_api.start_api()

                    if image_files:
                        self.logger.debug("Message contains image files, processing images")
                        response = await self.llama_api.send_request(self.context_config.get_setting('multimodal_context'), cleaned_prompt, image_files=image_files)
                    else:
                        response = await self.llama_api.send_request(self.context_config.get_setting('main_context'), cleaned_prompt, image_files=[])

                    self.logger.debug(f"Llama API response: {self.truncate_log(response)}")
                    if message_type == "simulate":
                        await self.handle_simulate_response(response, queued_message[1], queued_message[4], queued_message[5], queued_message[6], queued_message[7])
                    else:
                        await self.send_response_message(response, queued_message[1])
                    self.message_queue.task_done()
        except Exception as e:
            self.logger.error(f"Error in process_messages loop: {e}")
            self.logger.debug("Restarting process_messages loop")
            self.loop.create_task(self.process_messages())

    async def handle_simulate_response(self, response, channel, name1, context1, name2, context2):
        self.logger.debug(f"Handling simulation response: {response}")
        response_clean = self.clean_response(response, name1)
        await self.send_message(channel, name1, response_clean)
        current_name = name2
        current_context = context2
        last_name = name1
        while True:
            if channel.id not in self.conversation_channels:
                self.logger.debug("Channel closed, ending conversation")
                break

            prompt = f"{current_context} {response_clean}"
            self.logger.debug(f"Prompt for {current_name}: {prompt}")
            response = await self.llama_api.send_request(self.context_config.get_setting('main_context'), prompt)
            self.logger.debug(f"Llama API response for {current_name}: {response}")

            response_clean = self.clean_response(response, current_name)
            if not response_clean:
                self.logger.debug(f"No response received for {current_name, retrying}")
                time.sleep(1)
                response_clean = self.clean_response(await self.llama_api.send_request(self.context_config.get_setting('main_context'), prompt), current_name)

            await self.send_message(channel, current_name, response_clean)
            last_name, current_name, current_context = current_name, last_name, context1 if last_name == name2 else context2

    async def send_message(self, channel, name, content):
        self.logger.debug(f"Sending message from {name}: {content}")
        await channel.send(f"{name}: {content}")

    async def process_image_files(self, image_files, prompt):
        # Process image files using pytesseract and multimodal API
        self.logger.debug("Starting image file processing")
        try:
            image_copy = image_files[0]
            extracted_text = pytesseract.image_to_string(Image.open(BytesIO(image_copy)))
            if not extracted_text.strip():
                self.logger.debug("No text extracted from image, using multimodal API")
                return await self.multimodal_api.send_request(self.context_config.get_setting('multimodal_context'), prompt + "[img-10]", image_files)
            else:
                self.logger.debug(f"Extracted text from image using pytesseract: {extracted_text}")
                return await self.multimodal_api.send_request(self.context_config.get_setting('multimodal_context') + " Text was extracted from this image using pytesseract: " + extracted_text, prompt + "[img-10]", image_files)
        except Exception as e:
            self.logger.error("Failed to process request: %s. Error: %s", str(e), type(e).__name__)
            return ""

    async def send_response_message(self, response, message):
        # Send response message, handle large messages
        self.logger.debug(f"Sending response message: {response}")
        response_clean = response.strip().replace('\n', ' ').replace('\r', ' ')
        try:
            if len(response_clean) <= 1950:
                await message.channel.send(response_clean)
            else:
                await self.send_large_message(response_clean, message.channel)
        except discord.errors.HTTPException as e:
            if e.code == 50006:  # Cannot send an empty message
                await message.channel.send("Got an empty response from the model, please try again!")
            else:
                self.logger.error(f"Failed to send message: {e}")

    async def send_large_message(self, content, channel, chunk_size=1900):
        # Send large messages in chunks
        self.logger.debug("Sending large message in chunks")
        for start in range(0, len(content), chunk_size):
            end = start + chunk_size
            if end < len(content) and not content[end].isspace():
                end = content.rfind(' ', start, end)
            await channel.send(content[start:end])

    async def create_conversation_channel(self, guild, name):
        # Create a new text channel for conversation
        self.logger.debug(f"Creating conversation channel: {name}")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        try:
            channel = await guild.create_text_channel(name, overwrites=overwrites)
            self.conversation_channels.add(channel.id)
            self.logger.debug(f"Created channel: {channel.id}")
            return channel
        except discord.errors.Forbidden:
            self.logger.error("Missing permissions to create a channel.")
            return None

    async def change_nickname(self, guild, nickname):
        # Change the bot's nickname in the guild
        self.logger.debug(f"Changing nickname to: {nickname}")
        await guild.me.edit(nick=nickname)

    async def simulate_conversation(self, ctx, name1: str, context1: str, name2: str, context2: str):
        # Simulate a conversation between two AIs
        self.logger.debug(f"Starting simulation conversation between {name1} and {name2}")
        channel = await self.create_conversation_channel(ctx.guild, f"{name1}-{name2}-conversation")
        if channel is None:
            await ctx.send("I don't have permission to create a new channel. Please check my permissions and try again.")
            return

        try:
            # Start the Llama API if it's not running
            if not self.llama_api.is_running and not self.llama_api.in_startup:
                self.logger.debug("Llama API is not running, starting API")
                await self.llama_api.start_api()

            initial_prompt = f"{context1} You are {name1}. Start the conversation."
            self.logger.debug(f"Initial prompt for {name1}: {initial_prompt}")
            simulate_prompt = [initial_prompt, channel, [], "simulate", name1, context1, name2, context2]
            await self.message_queue.put(simulate_prompt)

        except Exception as e:
            self.logger.error(f"Error during simulated conversation: {e}")
        finally:
            await self.change_nickname(ctx.guild, None)

    def clean_response(self, response, name):
        # Clean the response text to ensure proper formatting and avoid double labels
        self.logger.debug(f"Cleaning response: {response}")
        response_clean = response.strip().replace('\n', ' ').replace('\r', ' ')
        if response_clean.lower().startswith(f"{name.lower()}:"):
            response_clean = response_clean[len(name)+1:].strip()
        self.logger.debug(f"Cleaned response: {response_clean}")
        return response_clean

    async def monitor_message_processing(self):
        while True:
            try:
                self.logger.debug("Starting the message processing loop")
                await self.process_messages()
            except Exception as e:
                self.logger.error(f"Message processing loop crashed: {e}")
                self.logger.debug("Clearing message queue and restarting message processing loop")
                self.message_queue = asyncio.Queue()
                await asyncio.sleep(1)  # Small delay to avoid tight loop in case of repeated failures

    def truncate_log(self, log_message, max_length=1000):
        if len(log_message) > max_length:
            return log_message[:max_length] + '... [truncated]'
        return log_message
