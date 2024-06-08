from discord_client import DiscordClient
from llama_api import LlamaAPI

if __name__ == "__main__":
    llama_api_instance = LlamaAPI()
    discord_client = DiscordClient(llama_api_instance, command_prefix='!')
    try:
        with open('token.txt', 'r') as file:
            discord_bot_token = file.read().strip()
        discord_client.run(discord_bot_token)
    except FileNotFoundError:
        print("Error: token.txt file not found. Please ensure the file exists and contains your bot token.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
