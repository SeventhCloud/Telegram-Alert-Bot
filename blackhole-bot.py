import asyncio
from dexscreener import DexscreenerClient
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    JobQueue
)
import logging
import os
import datetime

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Conversation States ---
SET_PAIR_ADDRESS, SET_PRICE_RANGE, SET_CHECK_INTERVAL, SET_CHAIN_ID = range(4)

class BlackholePriceBot:
    def __init__(self, token: str, chat_id: str):
        self.telegram_bot_token = token
        # Store as int for send_message, allow None if not set
        self.telegram_chat_id = int(chat_id) if chat_id else None 

        # Dynamic configuration variables, will be updated by commands
        self.current_dexscreener_chain_id = "avalanche"
        self.current_dexscreener_pair_address = "0x859592A4A469610E573f96Ef87A0e5565F9a94c8"
        self.current_price_threshold_lower = 1.0002
        self.current_price_threshold_upper = 1.0003 
        self.current_check_interval_seconds = 120
        self.alert_cooldown_seconds = 300 # 10 minutes default cooldown

        self.dexscreener_client = DexscreenerClient()
        self.monitor_job = None # To hold the scheduled job object

        self.application = Application.builder().token(self.telegram_bot_token).build()
        self._register_handlers()

    def _register_handlers(self):
        """Registers all command and conversation handlers."""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("status", self.status_command))

        # Conversation handlers
        self.application.add_handler(ConversationHandler(
            entry_points=[CommandHandler("setpair", self.set_pair_address_start)],
            states={
                SET_PAIR_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_pair_address_received)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        ))

        self.application.add_handler(ConversationHandler(
            entry_points=[CommandHandler("setrange", self.set_price_range_start)], # Renamed method
            states={
                SET_PRICE_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_price_range_received)], # Single state for parsing "x - y"
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        ))


        self.application.add_handler(ConversationHandler(
            entry_points=[CommandHandler("setinterval", self.set_check_interval_start)],
            states={
                SET_CHECK_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_check_interval_received)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        ))

        self.application.add_handler(ConversationHandler(
            entry_points=[CommandHandler("setchain", self.set_chain_id_start)],
            states={
                SET_CHAIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_chain_id_received)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        ))

        # Error handler
        self.application.add_error_handler(self.error_handler)

    async def _send_telegram_message(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_text: str):
        """Sends a message to the configured Telegram chat."""
        try:
            await context.bot.send_message(chat_id=chat_id, text=message_text, parse_mode='HTML')
            logger.info(f"Notification sent to Telegram chat {chat_id}: {message_text}")
        except Exception as e:
            logger.error(f"Error sending Telegram message to chat {chat_id}: {e}")

    async def _get_dex_pair_data(self, chain_id: str, pair_address: str):
        """
        Fetches the pair data from Dexscreener.
        Returns the pair data object or None if an error occurs or no data is found.
        """
        try:
            pairs_data = await self.dexscreener_client.get_token_pair_async(chain_id, pair_address)

            if pairs_data and pairs_data.base_token and pairs_data.quote_token:
                logger.info(f"Successfully fetched data for {pairs_data.base_token.symbol}/{pairs_data.quote_token.symbol} on {chain_id}.")
                return pairs_data
            else:
                logger.warning(f"No data found for pair {pair_address} on chain {chain_id}.")
                return None
        except Exception as e:
            logger.error(f"An error occurred while fetching Dexscreener data for {pair_address} on {chain_id}: {e}")
            return None

    async def _monitor_price_loop(self, context: ContextTypes.DEFAULT_TYPE):
        """Monitors the price and sends alerts if it drops below the threshold."""
        print(context.job.data)
        chat_id = context.job.data['chat_id'] # Get the chat_id from the job data
        
        # Ensure context.chat_data is a dictionary. For JobQueue, context.chat_data *should* be
        # correctly set by PTB when chat_id is passed in run_repeating.
        # If for some reason it's None (e.g., no persistence, or specific PTB version quirks),
        # initialize it as an empty dictionary for the current execution.
        # Note: Without persistence, this data will NOT survive bot restarts.
        if context.chat_data is None:
            context.chat_data = {}
            logger.warning(f"context.chat_data was None for chat {chat_id} in job. Initializing locally for this run. "
                           "Consider adding persistence to Application for data to survive restarts.")
        
        # Use context.chat_data directly
        # Initialize if not present
        if 'last_alert_time' not in context.chat_data:
            context.chat_data['last_alert_time'] = None
        last_alert_time = context.chat_data['last_alert_time']


        logger.info(f"Monitor running for chat {chat_id} with pair {self.current_dexscreener_pair_address} on {self.current_dexscreener_chain_id} (interval: {self.current_check_interval_seconds}s)")

        # Use instance variables for configuration (they are already updated by set commands)
        chain_id = self.current_dexscreener_chain_id
        pair_address = self.current_dexscreener_pair_address
        alert_cooldown = self.alert_cooldown_seconds

        pairs_data = await self._get_dex_pair_data(chain_id, pair_address)

        if pairs_data:
            current_price_native = float(pairs_data.price_native)
            logger.info(f"{pairs_data.base_token.symbol}/{pairs_data.quote_token.symbol} - Current Price {pairs_data.quote_token.symbol}: ${current_price_native:.6f}")
            
            if not (current_price_native >= self.current_price_threshold_lower and current_price_native <= self.current_price_threshold_upper):
                current_time = datetime.datetime.now().timestamp()
                if last_alert_time is None or (current_time - last_alert_time) > alert_cooldown:
                    message = (
                        f"🚨 **PRICE ALERT!** 🚨\n\n"
                        f"The price of {pairs_data.base_token.symbol} got out of Range ${self.current_price_threshold_lower} - {self.current_price_threshold_upper}!\n"
                        f"Current Price: **${current_price_native:.6f} USD**\n"
                        f"Pool: <a href='{pairs_data.url}'>{pairs_data.base_token.symbol}/{pairs_data.quote_token.symbol} on {pairs_data.dex_id}</a>\n"
                        f"Chain: {pairs_data.chain_id.capitalize()}"
                    )
                    await self._send_telegram_message(context, chat_id, message)
                    context.chat_data['last_alert_time'] = current_time # Update in chat_data
                else:
                    logger.info(f"Price below threshold, but still in cooldown period ({(alert_cooldown - (current_time - last_alert_time)) / 60:.1f} minutes remaining).")
            else:
                # If price is back above threshold, reset cooldown
                if last_alert_time is not None:
                    logger.info("Price is back above threshold. Resetting alert cooldown.")
                    context.chat_data['last_alert_time'] = None 
                    # Also clear the fetch error alert if price is back to normal
                    if 'last_fetch_error_alert' in context.chat_data:
                        del context.chat_data['last_fetch_error_alert']
        else:
            logger.warning("Skipping price check due to previous data fetching error.")
            # If there's an error fetching data, send a warning to the user if it's the first time
            if 'last_fetch_error_alert' not in context.chat_data or \
               (datetime.datetime.now().timestamp() - context.chat_data['last_fetch_error_alert']) > alert_cooldown: # Use alert_cooldown for this too
                await self._send_telegram_message(context, chat_id,
                                                   "⚠️ **Warning:** Could not fetch price data from Dexscreener. The monitor will retry.")
                context.chat_data['last_fetch_error_alert'] = datetime.datetime.now().timestamp()
            else:
                logger.debug("Skipping fetch error alert due to cooldown.")

    # --- Telegram Bot Command Handlers (now methods of the class) ---

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sends a message when the command /start is issued and starts monitoring."""
        chat_id = update.effective_chat.id

        # Stop any existing monitoring task for this chat
        current_jobs = context.job_queue.get_jobs_by_name(f"price_monitor_{chat_id}")
        for job in current_jobs:
            job.schedule_removal()
            logger.info(f"Existing monitoring job '{job.name}' for chat {chat_id} cancelled and removed.")

        # Schedule the new monitoring job
        self.monitor_job = context.job_queue.run_repeating(
            self._monitor_price_loop,
            interval=self.current_check_interval_seconds,
            first=0, # Run immediately once
            # Passing chat_id here helps PTB associate chat_data with the job context
            data={'chat_id': chat_id}, # <--- CHANGE HERE
            chat_id=chat_id, 
            name=f"price_monitor_{chat_id}"
        )
        logger.info(f"Price monitor for chat {chat_id} scheduled to run every {self.current_check_interval_seconds} seconds.")

        message = (
            "Hello! I'm your Crypto Price Alert Bot. 🚀\n\n"
            "I'm now monitoring the price.\n"
            "You can configure me using these commands:\n"
            "/setpair - Set the Dexscreener pair address.\n"
            "/setrange - Set the price threshold.\n"
            "/setinterval - Set the check interval in seconds.\n"
            "/setchain - Set the Dexscreener chain ID.\n"
            "/status - Get the current monitoring status and settings.\n"
            "/stop - Stop the price monitoring."
        )
        await self._send_telegram_message(context, chat_id, message)

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Stops the price monitoring."""
        chat_id = update.effective_chat.id
        jobs_to_remove = context.job_queue.get_jobs_by_name(f"price_monitor_{chat_id}")

        if jobs_to_remove:
            for job in jobs_to_remove:
                job.schedule_removal() # Removes the job from the queue
                logger.info(f"Price monitoring job '{job.name}' for chat {chat_id} stopped and removed.")
            self.monitor_job = None # Clear global reference if all jobs are removed
            await self._send_telegram_message(context, chat_id, "Price monitoring has been stopped.")
        else:
            await self._send_telegram_message(context, chat_id, "No active price monitoring to stop for this chat.")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Shows the current monitoring status and settings."""
        
        monitor_active = bool(context.job_queue.get_jobs_by_name(f"price_monitor_{update.effective_chat.id}"))

        upper_threshold_display = f"${self.current_price_threshold_upper:.6f}" if self.current_price_threshold_upper is not None else "Disabled"

        message = (
            "📊 Current Monitoring Status:\n\n"
            f"Chain ID: {self.current_dexscreener_chain_id}\n"
            f"Pair Address: {self.current_dexscreener_pair_address}\n"
            f"Lower Price Threshold: ${self.current_price_threshold_lower:.6f}\n"
            f"Upper Price Threshold: {upper_threshold_display}\n"
            f"Check Interval: {self.current_check_interval_seconds} seconds\n"
            f"Alert Cooldown: {self.alert_cooldown_seconds} seconds\n\n"
            f"Monitoring active: {'Yes' if monitor_active else 'No'}"
        )
        await self._send_telegram_message(context, update.effective_chat.id, message)

    # --- Conversation Handlers (now methods of the class) ---

    async def set_pair_address_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Asks the user for the new pair address."""
        await self._send_telegram_message(context, update.effective_chat.id, "Please send me the new Dexscreener **pair address**:")
        return SET_PAIR_ADDRESS

    async def set_pair_address_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receives the pair address and updates the setting."""
        new_address = update.message.text.strip()

        if len(new_address) == 42 and new_address.startswith('0x'): # Basic validation
            self.current_dexscreener_pair_address = new_address
            await self._send_telegram_message(context, update.effective_chat.id,
                                               f"✅ Pair address updated to: {self.current_dexscreener_pair_address}. Restarting monitor to apply.")
            await self.start_command(update, context) # Restart monitor with new settings
            return ConversationHandler.END
        else:
            await self._send_telegram_message(context, update.effective_chat.id,
                                               "❌ Invalid pair address format. Please send a valid 0x... address (42 characters long).\n"
                                               "Or send /cancel to abort.")
            return SET_PAIR_ADDRESS

    async def set_price_range_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Asks the user for the new price range in 'x - y' format."""
        await self._send_telegram_message(context, update.effective_chat.id, 
                                           "Please send me the **price range** in lower - upper format (e.g., 1.0000 - 1.0005).\n"
                                           "Send X - none or X - 0 if you only want a lower limit.")
        return SET_PRICE_RANGE

    async def set_price_range_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receives the price range 'x - y' and updates the settings."""
        input_text = update.message.text.strip()
        parts = [p.strip() for p in input_text.split('-')]

        if len(parts) != 2:
            await self._send_telegram_message(context, update.effective_chat.id,
                                               "❌ Invalid format. Please send the range as lower - upper (e.g., 1.0000 - 1.0005).\n"
                                               "Or send /cancel to abort.")
            return SET_PRICE_RANGE

        try:
            lower_str, upper_str = parts[0], parts[1]

            new_lower_price = float(lower_str)
            if new_lower_price <= 0:
                raise ValueError("Lower price threshold must be positive.")
            
            new_upper_price = None
            if upper_str.lower() not in ['0', 'none']:
                new_upper_price = float(upper_str)
                if new_upper_price <= 0:
                    raise ValueError("Upper price threshold must be positive.")
                
                if new_upper_price < new_lower_price:
                    await self._send_telegram_message(context, update.effective_chat.id,
                                                       f"❌ Upper threshold (${new_upper_price:.6f}) cannot be less than the lower threshold (${new_lower_price:.6f}).\n"
                                                       "Please send a valid range.\n"
                                                       "Or send /cancel to abort.")
                    return SET_PRICE_RANGE

            self.current_price_threshold_lower = new_lower_price
            self.current_price_threshold_upper = new_upper_price

            message = f"✅ Price thresholds updated!\n" \
                      f"Lower: ${self.current_price_threshold_lower:.6f}\n"
            if self.current_price_threshold_upper is not None:
                message += f"Upper: ${self.current_price_threshold_upper:.6f}\n"
            else:
                message += "Upper: Disabled (monitoring for drop below lower limit only)\n"
            message += "The monitor will use these new thresholds on its next check."
            
            await self._send_telegram_message(context, update.effective_chat.id, message)
            return ConversationHandler.END
        
        except ValueError as e:
            await self._send_telegram_message(context, update.effective_chat.id,
                                               f"❌ Invalid price value: {e}. Please ensure both values are positive numbers.\n"
                                               "Example: 1.0000 - 1.0005 or 1.0000 - none.\n"
                                               "Or send /cancel to abort.")
            return SET_PRICE_RANGE
        

    async def set_check_interval_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Asks the user for the new check interval."""
        await self._send_telegram_message(context, update.effective_chat.id, "Please send me the new **check interval** in seconds (e.g., 60, 120):")
        return SET_CHECK_INTERVAL

    async def set_check_interval_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receives the check interval and updates the setting."""
        try:
            new_interval = int(update.message.text.strip())
            if new_interval <= 0:
                raise ValueError("Interval must be positive.")
            self.current_check_interval_seconds = new_interval
            await self._send_telegram_message(context, update.effective_chat.id,
                                               f"✅ Check interval updated to: {self.current_check_interval_seconds} seconds. Restarting monitor to apply immediately.")
            await self.start_command(update, context) # Restart monitor with new interval
            return ConversationHandler.END
        except ValueError:
            await self._send_telegram_message(context, update.effective_chat.id,
                                               "❌ Invalid interval. Please send a positive integer (e.g., 60).\n"
                                               "Or send /cancel to abort.")
            return SET_CHECK_INTERVAL

    async def set_chain_id_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Asks the user for the new chain ID."""
        await self._send_telegram_message(context, update.effective_chat.id, "Please send me the new **chain ID** (e.g., ethereum, avalanche):")
        return SET_CHAIN_ID

    async def set_chain_id_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receives the chain ID and updates the setting."""
        new_chain_id = update.message.text.strip().lower() # Convert to lowercase for consistency
        
        self.current_dexscreener_chain_id = new_chain_id
        await self._send_telegram_message(context, update.effective_chat.id,
                                           f"✅ Chain ID updated to: {self.current_dexscreener_chain_id}. Restarting monitor to apply.")
        await self.start_command(update, context) # Restart monitor with new settings
        return ConversationHandler.END

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancels the current conversation."""
        await self._send_telegram_message(context, update.effective_chat.id, "Operation cancelled.")
        return ConversationHandler.END

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and send a message to the user."""
        logger.error("Exception while handling an update:", exc_info=context.error)

        chat_id_to_send_error = None

        # Try to get chat_id from update first (for errors from direct user interactions)
        if update and update.effective_chat:
            chat_id_to_send_error = update.effective_chat.id
        # If update is None (e.g., error from a JobQueue), try to get chat_id from job data
        # context.job.data is reliable for jobs
        elif context.job and context.job.data and 'chat_id' in context.job.data:
            chat_id_to_send_error = context.job.data['chat_id']
        # Fallback to the predefined TELEGRAM_CHAT_ID if no specific chat_id can be determined
        elif self.telegram_chat_id:
            chat_id_to_send_error = self.telegram_chat_id

        if chat_id_to_send_error:
            await self._send_telegram_message(context, chat_id_to_send_error,
                                            "An internal error occurred. Please try again or support.")
        else:
            logger.warning("Could not determine chat_id to send error message. Error was logged.")

    def run(self):
        """Starts the bot."""
        logger.info("Bot starting...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot stopped.")

if __name__ == "__main__":
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # Used for initial setup/admin

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        exit(1)
    # Changed to warning, as your code handles None for TELEGRAM_CHAT_ID.
    if not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_CHAT_ID environment variable not set. The bot will rely on chat_id from /start command for sending alerts.")

    bot = BlackholePriceBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    bot.run()