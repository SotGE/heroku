# Municipal Services Telegram Bot

## Overview
This Telegram bot provides municipal services information and support, offering:
- Interactive menu with various service sections
- Free chat mode for specific queries
- Document template generation

## Features
- Multiple service sections:
  - Качество коммунальных услуг
  - Управление многоквартирными домами
  - Договоры и документы
  - Ресурсоснабжение
  - Обращения с ТКО
  - Частные домовладения

- Document Generation: Create personalized documents using Word templates

## Setup

### Prerequisites
- Python 3.9+
- Telegram Bot Token
- Mistral AI API Key

### Installation
1. Clone the repository
2. Create a virtual environment
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration
1. Create a `.env` file with:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   MISTRAL_API_KEY=your_mistral_api_key
   ```

### Running the Bot
```bash
python bot.py
```

## Bot Commands
- `/start`: Initialize the bot
- `/main`: Open main menu
- `/chat`: Enter free question mode

## Project Structure
```
hero/
├── bot.py           # Main bot logic
├── .env             # Environment variables
├── requirements.txt # Python dependencies
├── menu_sections/   # Q&A content for different sections
├── templates/       # Document templates
└── knowledge_base/  # Additional knowledge base documents
```

## Contributing
Feel free to open issues or submit pull requests.

## License
[Your License Here]
