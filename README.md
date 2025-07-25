# 🚀 Crypto Range Alert Bot

A powerful and configurable Telegram bot that keeps you informed about cryptocurrency price movements. Set custom price ranges (lower and upper bounds) for your favorite tokens across various chains, and receive instant alerts directly in your Telegram chat when the price moves outside your defined thresholds.

## ✨ Features

* **Custom Price Ranges:** Define both lower and upper price thresholds (e.g., `1.0000 - 1.0005`) for any token pair.
* **Single-Sided Alerts:** Optionally set only a lower limit (e.g., `1.0000 - none`) to get alerts only when the price drops below it.
* **Multi-Chain Support:** Monitor token prices on various blockchain networks supported by Dexscreener.
* **Real-time Monitoring:** Continuously fetches price data at a user-defined interval (e.g., every 5 seconds).
* **Intelligent Cooldown:** Implements a configurable cooldown period after an alert to prevent spamming your chat.
* **User-Friendly Commands:** All configurations (pair address, chain, price range, check interval) are handled interactively via intuitive Telegram commands.
* **Status Overview:** Get a quick summary of your current monitoring settings and bot status at any time.
* **Robust Error Handling:** Notifies you of data fetching issues and other internal errors to keep you informed of the bot's health.

## 💡 Why Use This Bot?

In the fast-paced world of cryptocurrency, missing critical price movements can lead to missed opportunities or significant losses. This bot acts as your personal automated market watcher, ensuring you're immediately notified when a token's price goes above or below your desired levels. It's ideal for:

* **Traders:** Quickly react to entry or exit points.
* **Investors:** Monitor your holdings and respond to sudden market changes.
* **Enthusiasts:** Stay updated on tokens you're following without constant manual checks.

## 🛠️ Technologies Used

* **Python:** The core programming language.
* **`python-telegram-bot`:** For seamless interaction with the Telegram Bot API.
* **`dexscreener-python`:** To reliably fetch real-time cryptocurrency pair data from Dexscreener's API, which uses **pair addresses**.
* **`asyncio`:** For efficient asynchronous operations and concurrent tasks.
* **Docker & Docker Compose:** For containerization and easy deployment.

## 🚀 Getting Started

The easiest way to get this bot running is by using Docker Compose.

### Prerequisites

* [Docker](https://docs.docker.com/get-docker/) installed on your system.
* A Telegram account to create your bot.

### 🐳 Deployment with Docker Compose (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git) # Replace with your actual repo URL
    cd your-repo-name
    ```
2.  **Get your Telegram Bot Token:**
    * Talk to [@BotFather](https://t.me/BotFather) on Telegram.
    * Send `/newbot` and follow the instructions to create a new bot.
    * BotFather will give you an **HTTP API Token**. Keep this token absolutely secure!

3.  **Configure Environment Variables:**
    Create a `.env` file in the root directory of the cloned repository (the same directory as `docker-compose.yml` and `Dockerfile`).
    Add the following lines to it, replacing the placeholder values:

    ```env
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN_HERE"
    TELEGRAM_CHAT_ID="YOUR_TELEGRAM_CHAT_ID_HERE" # Optional: The initial chat ID for the bot to send messages. If not set, the bot will start monitoring for the chat that first sends `/start`.
    ```
    *Note: Docker Compose will automatically pick up variables from this `.env` file.*

4.  **Build and Run the Bot:**
    Navigate to the project's root directory in your terminal and run:
    ```bash
    docker compose up --build -d
    ```
    * `--build`: Builds the Docker image from the `Dockerfile`. You only need this on the first run or after making changes to the `Dockerfile`.
    * `-d`: Runs the containers in detached mode (in the background).

5.  **Check Logs (Optional):**
    To see the bot's output and verify it's running:
    ```bash
    docker compose logs -f
    ```

6.  **Stop the Bot:**
    To stop and remove the running containers:
    ```bash
    docker compose down
    ```

### 🐍 Manual Installation (Alternative)

If you prefer to run the bot directly on your system without Docker:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/SeventhCloud/Telegram-Alert-Bot.git](https://github.com/SeventhCloud/Telegram-Alert-Bot.git)
    cd Telegram-Alert-Bot
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: .\venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install python-telegram-bot dexscreener-python
    ```
4.  **Set Environment Variables:**
    Set `TELEGRAM_BOT_TOKEN` and optionally `TELEGRAM_CHAT_ID` as environment variables in your system's shell (e.g., `export TELEGRAM_BOT_TOKEN="YOUR_TOKEN"` on Linux/macOS, or via system settings on Windows).

5.  **Run the Bot:**
    ```bash
    python your_main_bot_file.py # Replace 'your_main_bot_file.py' with the actual name of your Python script (e.g., `bot.py` or `main.py`)
    ```

## 💬 Usage (via Telegram)

Once the bot is running (either via Docker or manually) and you've sent it the `/start` command in Telegram, you can use the following commands:

1.  **`/start`**: Initiates the bot and begins (or restarts) price monitoring with current settings.
2.  **`/setchain`**: Set the Dexscreener chain ID (e.g., `avalanche`, `ethereum`, `bsc`, `polygon`).
3.  **`/setpair`**: Set the **Dexscreener pair address** (e.g., `0x859592A4A469610E573f96Ef87A0e5565F9a94c8`). You can find this on Dexscreener.com for any token pair.
4.  **`/setprice`**: Define your price alert range. Send in `lower - upper` format (e.g., `1.0000 - 1.0005`).
    * To set only a lower limit: `1.0000 - none` (or `1.0000 - 0`).
5.  **`/setinterval`**: Set how often the bot checks the price, in seconds (e.g., `60` for 1 minute).
6.  **`/status`**: Displays all current monitoring configurations and whether monitoring is active.
7.  **`/stop`**: Halts the price monitoring process.
8.  **`/cancel`**: Exits any active configuration conversation (e.g., if you're in the middle of `/setprice`).

## 🤝 Contributing

Contributions are welcome! If you have ideas for improvements, new features, or bug fixes, feel free to:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature`).
3.  Make your changes.
4.  Commit your changes (`git commit -am 'Add new feature'`).
5.  Push to the branch (`git push origin feature/your-feature`).
6.  Create a new Pull Request.

Please ensure your code adheres to good practices and includes relevant tests if applicable.

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).

---