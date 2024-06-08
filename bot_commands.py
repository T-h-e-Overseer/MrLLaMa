from discord.ext import commands
import discord
import asyncio
import os

@commands.command(name='set')
async def set_config(ctx, setting: str, value: str = None):
    """Dynamically sets configuration values, lists models, or switches models."""
    if ctx.bot.debug_bot_commands:
        ctx.bot.logger.debug("Received command name %s with setting: %s value: %s", ctx.command.name, setting, value)

    if setting == 'defaults':
        # Reset settings to defaults for the current model
        default_model = ctx.bot.llama_api.configurable.defaults['selected_model']
        ctx.bot.llama_api.configurable.set_model(default_model)
        await ctx.send(f"All settings have been reset to default values for the model: {default_model}\n"
                       + ctx.bot.llama_api.configurable.format_settings('\n'))

        if ctx.bot.debug_bot_commands:
            ctx.bot.logger.debug("Settings after reset to defaults: %s", 
                                 ctx.bot.llama_api.configurable.format_settings(', '))
    elif setting == 'list':
        # List current settings including context settings
        settings_message = ctx.bot.llama_api.configurable.format_settings('\n')
        context_settings_message = ctx.bot.context_config.format_settings('\n')
        await ctx.send("Current settings:\n" + settings_message + "\n\nContext settings:\n" + context_settings_message)
        if ctx.bot.debug_bot_commands:
            ctx.bot.logger.debug("List settings request received, listing: %s\n%s", settings_message, context_settings_message)
    elif setting == 'model-list':
        # List all available models and their settings
        models_info = '\n'.join(f"{model}: {settings}" for model, settings in ctx.bot.llama_api.configurable.models.items())
        await ctx.send(f"Available models and their default settings:\n{models_info}")
        if ctx.bot.debug_bot_commands:
            ctx.bot.logger.debug("Model list requested: %s", models_info)
    elif setting == 'model':
        # Change the current model
        if value in ctx.bot.llama_api.configurable.models:
            ctx.bot.llama_api.configurable.set_model(value)
            await ctx.send(f"Model changed to {value}. New settings:\n"
                           + ctx.bot.llama_api.configurable.format_settings('\n'))
            if ctx.bot.debug_bot_commands:
                ctx.bot.logger.debug("Model changed to %s, settings: %s", value, ctx.bot.llama_api.configurable.format_settings(', '))
        else:
            await ctx.send(f"Model name '{value}' not recognized. Use 'set model list' to see available models.")
            if ctx.bot.debug_bot_commands:
                ctx.bot.logger.debug("Attempted to change to unrecognized model: %s", value)
    elif setting in ctx.bot.context_config.list_settings():
        # Set context settings
        ctx.bot.context_config.update_setting(setting, value)
        await ctx.send(f"{setting} set to: {value}")
        if ctx.bot.debug_bot_commands:
            ctx.bot.logger.debug(f"{setting} set to: {value}")
    else:
        # Set individual settings for the model
        if value is None:
            await ctx.send("Please provide a value for the setting.")
            return

        if setting in ctx.bot.llama_api.configurable.defaults:
            try:
                default_type = type(ctx.bot.llama_api.configurable.defaults[setting])
                converted_value = default_type(value)
                ctx.bot.llama_api.configurable.update_setting(setting, converted_value)
                await ctx.send(f"{setting} set to {converted_value}.")
                if ctx.bot.debug_bot_commands:
                    ctx.bot.logger.debug("Settings after change: %s", ctx.bot.llama_api.configurable.format_settings(', '))
            except ValueError:
                await ctx.send(f"Invalid type for value. Setting {setting} needs type {default_type.__name__}.")
            except Exception as e:
                await ctx.send(f"An unknown error occurred: {str(e)}")
                if ctx.bot.debug_bot_commands:
                    ctx.bot.logger.debug(f"Failed to change {setting} due to an unexpected error. Current settings: {ctx.bot.llama_api.configurable.format_settings(', ')}")
        else:
            await ctx.send(f"Setting {setting} not recognized.")
            if ctx.bot.debug_bot_commands:
                ctx.bot.logger.debug("Attempted to change unrecognized setting. Current settings: %s", ctx.bot.llama_api.configurable.format_settings(', '))

@commands.command(name='api')
async def api_state(ctx, action: str, value: str = None):
    """Controls and monitors the Llama API state."""
    if action == 'stop':
        # Stop the Llama API
        ctx.bot.llama_api.stop_api()
        await asyncio.sleep(1)  # Use asyncio.sleep instead of time.sleep
        await ctx.send(f"Sent command to terminate Llama API. Current state: is_running {ctx.bot.llama_api.is_running}, in_startup {ctx.bot.llama_api.in_startup}")
    
    elif action == 'start':
        # Start the Llama API
        if ctx.bot.llama_api.is_running or ctx.bot.llama_api.in_startup:
            await ctx.send(f"Can't start API in current state: is_running {ctx.bot.llama_api.is_running}, in_startup {ctx.bot.llama_api.in_startup} - Try api stop")
        else:
            await ctx.bot.llama_api.start_api()  # Ensure this is awaited if it's an async function
            await asyncio.sleep(1)
            await ctx.send(f"Sent API start signal. Current state: is_running {ctx.bot.llama_api.is_running}, in_startup {ctx.bot.llama_api.in_startup}")
    
    elif action == 'state':
        # Check the current state of the Llama API
        await ctx.send(f"Current Llama API state: is_running {ctx.bot.llama_api.is_running}, in_startup {ctx.bot.llama_api.in_startup}")
    
    elif action == 'log':
        # Retrieve log lines
        if value:
            num_lines = int(value)
            log_content = await get_log_lines(num_lines)
            if log_content:
                if len(log_content) > 1950:
                    with open("log.txt", "w") as file:
                        file.write(log_content)
                    await ctx.send(file=discord.File("log.txt"))
                    os.remove("log.txt")
                else:
                    await ctx.send(f"```{log_content}```")
            else:
                await ctx.send("No log content available.")
        else:
            await ctx.send("Please specify the number of log lines to retrieve.")
    
    elif action == 'code':
        # Example for handling 'code' action
        pass
    
    else:
        await ctx.send("Invalid usage, api actions are stop, start, state, log <lines>, code [<filename>, list]")

@commands.command(name='simulate')
async def start_simulation(ctx, name1: str, context1: str, name2: str, context2: str):
    # Start a simulated conversation between two AIs
    await ctx.bot.simulate_conversation(ctx, name1, context1, name2, context2)

async def get_log_lines(num_lines):
    """Fetches the specified number of log lines from the latest log files."""
    log_files = ['discordbot.log'] + [f'discordbot.log.{i}' for i in range(1, 6)]
    log_lines = []

    # Read lines from log files in order of newest to oldest
    for log_file in log_files:
        if os.path.exists(log_file):
            with open(log_file, 'r') as file:
                log_lines.extend(file.readlines())
        if len(log_lines) >= num_lines:
            break

    return ''.join(log_lines[-num_lines:])
