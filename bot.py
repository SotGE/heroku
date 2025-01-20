import os
import logging
import sys
import traceback
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from docxtpl import DocxTemplate
import uuid
import asyncio
from flask import Flask, request, jsonify
import random

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'  # Logs will be written to a file
)
logger = logging.getLogger(__name__)

# Initialize Mistral client
mistral_client = MistralClient(api_key=os.getenv("MISTRAL_API_KEY"))

# Initialize vector store
embeddings = HuggingFaceEmbeddings()
documents_path = "knowledge_base"
if not os.path.exists(documents_path):
    os.makedirs(documents_path)

# Menu sections
MENU_SECTIONS = [
    "Качество коммунальных услуг",
    "Управление многоквартирными домами",
    "Договоры и документы",
    "Ресурсоснабжение",
    "Обращения с ТКО",
    "Частные домовладения"
]

# Conversation states
MAIN_MENU, SECTION_MENU, DOCUMENT_TEMPLATE, DOCUMENT_FIO, DOCUMENT_AGE, DOCUMENT_PHONE, DOCUMENT_EMAIL = range(7)

def load_documents():
    """Load and process documents from the knowledge base"""
    loader = DirectoryLoader(documents_path, glob="**/*.txt")
    documents = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    texts = text_splitter.split_documents(documents)
    
    return Chroma.from_documents(texts, embeddings)

# Load vector store
vector_store = load_documents()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    keyboard = [
        ['/main - Открыть меню'],
        ['/chat - Свободный вопрос'],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        'Привет! Выберите режим работы:', 
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display main menu with sections"""
    keyboard = [[section] for section in MENU_SECTIONS]
    keyboard.append(['Назад'])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        'Выберите раздел:', 
        reply_markup=reply_markup
    )
    return SECTION_MENU

async def section_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle section selection"""
    section = update.message.text
    
    if section == 'Назад':
        return await start(update, context)
    
    if section == 'Договоры и документы':
        keyboard = [
            ['Шаблон заявления'],
            ['Назад']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            'Выберите действие:', 
            reply_markup=reply_markup
        )
        return DOCUMENT_TEMPLATE
    
    # For other sections, generate and show predefined Q&A
    section_path = os.path.join('menu_sections', section.replace(' ', '_'))
    files = os.listdir(section_path)
    
    if not files:
        await update.message.reply_text('В этом разделе пока нет информации.')
        return SECTION_MENU
    
    # Randomly select a file and show its content
    import random
    selected_file = random.choice(files)
    with open(os.path.join(section_path, selected_file), 'r', encoding='utf-8') as f:
        content = f.read()
    
    keyboard = [
        ['Еще вопрос'],
        ['Назад']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(content, reply_markup=reply_markup)
    return SECTION_MENU

async def document_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start document template process"""
    if update.message.text == 'Назад':
        return await main_menu(update, context)
    
    await update.message.reply_text('Введите ваше ФИО:')
    return DOCUMENT_FIO

async def document_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capture FIO for document"""
    context.user_data['fio'] = update.message.text
    await update.message.reply_text('Введите ваш возраст:')
    return DOCUMENT_AGE

async def document_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capture age for document"""
    context.user_data['age'] = update.message.text
    await update.message.reply_text('Введите ваш телефон:')
    return DOCUMENT_PHONE

async def document_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capture phone for document"""
    context.user_data['phone'] = update.message.text
    await update.message.reply_text('Введите ваш email:')
    return DOCUMENT_EMAIL

async def document_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate document with user details"""
    context.user_data['email'] = update.message.text
    
    # Use a template
    template_path = 'templates/заявление.docx'
    document = DocxTemplate(template_path)
    
    # Render the document
    context_dict = {
        'fio': context.user_data['fio'],
        'age': context.user_data['age'],
        'phone': context.user_data['phone'],
        'email': context.user_data['email']
    }
    document.render(context_dict)
    
    # Save with unique filename
    filename = f'заявление_{uuid.uuid4()}.docx'
    document.save(filename)
    
    # Send the document
    with open(filename, 'rb') as file:
        await update.message.reply_document(file)
    
    # Clean up
    os.remove(filename)
    
    keyboard = [
        ['/main - Открыть меню'],
        ['/chat - Свободный вопрос'],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        'Документ сгенерирован. Выберите следующее действие:', 
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages in free chat mode"""
    question = update.message.text
    
    # Search in vector store
    docs = vector_store.similarity_search(question, k=2)
    
    if not docs:
        await update.message.reply_text(
            "Извините, я не нашел информации по вашему вопросу в базе знаний."
        )
        return
    
    # Prepare context from relevant documents
    context_text = "\n".join([doc.page_content for doc in docs])
    
    # Prepare prompt for Mistral
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant. Answer the question based only on the provided context. If you cannot answer the question based on the context, say so."),
        ChatMessage(role="user", content=f"Context: {context_text}\n\nQuestion: {question}\n\nAnswer based only on the provided context."),
    ]
    
    try:
        # Get response from Mistral
        chat_response = mistral_client.chat(
            model="mistral-tiny",
            messages=messages,
        )
        
        response = chat_response.messages[0].content
        
        # Check if the response indicates inability to answer
        if "cannot" in response.lower() or "don't have" in response.lower():
            await update.message.reply_text(
                "Извините, я не могу ответить на этот вопрос на основе имеющейся информации."
            )
        else:
            await update.message.reply_text(response)
            
    except Exception as e:
        logger.error(f"Error while getting response from Mistral: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
        )

# Flask app for webhook
app = Flask(__name__)

# Global variable for bot application
application = None

async def start_webhook(bot_token, webhook_url):
    """Initialize webhook"""
    global application
    application = Application.builder().token(bot_token).build()

    # Setup handlers (as before)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('main', main_menu),
            CommandHandler('chat', lambda update, context: update.message.reply_text('Задайте свой вопрос.'))
        ],
        states={
            # Your existing conversation states
            MAIN_MENU: [
                MessageHandler(filters.Regex('^/main'), main_menu)
            ],
            # ... other states as before
        },
        fallbacks=[CommandHandler('start', start)]
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Set webhook
    await application.bot.set_webhook(url=webhook_url)
    return application

@app.route(f'/{os.getenv("TELEGRAM_BOT_TOKEN")}', methods=['POST'])
def webhook():
    """Webhook handler"""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.create_task(application.process_update(update))
        return "OK"
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        logger.error(traceback.format_exc())
        return "Error", 500

def init_webhook():
    """Initialize webhook on app start"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if not bot_token or not webhook_url:
        logger.error("TOKEN or WEBHOOK_URL not specified")
        sys.exit(1)
    
    asyncio.run(start_webhook(bot_token, webhook_url))

if __name__ == '__main__':
    init_webhook()
