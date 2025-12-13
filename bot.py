import logging
import os
import json

# --- FIX FOR APSCHEDULER TIMEZONE ERROR ---
try:
    import pytz
    import apscheduler.util
    apscheduler.util.astimezone = lambda tz: pytz.utc
except ImportError:
    pass
# ------------------------------------------

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Get the directory where the script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")

# Load data
with open(DATA_FILE, "r", encoding='utf-8') as f:
    DATA = json.load(f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a styled welcome message."""
    keyboard = []
    row = []
    for y in DATA.keys():
        row.append(InlineKeyboardButton(f"🎓 Year {y}", callback_data=f"year:{y}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if this is a callback (Back button) or a command (/start)
    # Check if this is a callback (Back button) or a command (/start)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "👋 *Welcome to the Telecom Resources Bot!* 🚀\n\n"
            "📚 Access slides, past questions, and books easily.\n"
            "👇 *Select your Year to get started:*",
            reply_markup=reply_markup, 
            parse_mode="Markdown"
        )
    else:
        # /start command typed: Clear old menu to keep chat clean
        last_menu_id = context.user_data.get("last_menu_id")
        if last_menu_id:
            try:
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=last_menu_id)
            except Exception:
                pass # Message might be too old or already deleted

        msg = await update.message.reply_text(
            "👋 *Welcome to the Telecom Resources Bot!* 🚀\n\n"
            "📚 Access slides, past questions, and books easily.\n"
            "👇 *Select your Year to get started:*",
            reply_markup=reply_markup, 
            parse_mode="Markdown"
        )
        context.user_data["last_menu_id"] = msg.message_id

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    data = query.data
    await query.answer()

    # -----------------------
    # Back to Home
    # -----------------------
    if data == "home":
        await start(update, context)
        return

    # -----------------------
    # Step 1: Select Year
    # -----------------------
    if data.startswith("year:"):
        year = data.split(":")[1]
        context.user_data["year"] = year

        keyboard = [
            [
                InlineKeyboardButton("Semester 1 🍂", callback_data=f"sem:1"),
                InlineKeyboardButton("Semester 2 🌸", callback_data=f"sem:2")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="home")]
        ]
        
        await query.edit_message_text(
            f"🎓 *Year {year} Selected*\n\n👇 Choose your semester:",
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )
        return

    # -----------------------
    # Step 2: Select Semester
    # -----------------------
    if data.startswith("sem:"):
        semester = data.split(":")[1]
        context.user_data["semester"] = semester
        year = context.user_data["year"]

        # Get courses
        courses = list(DATA[year][semester].keys())
        
        keyboard = []
        for course in courses:
            keyboard.append([InlineKeyboardButton(f"📘 {course}", callback_data=f"course:{course}")])
        
        # Back button goes to Year selection
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"year:{year}")])

        await query.edit_message_text(
            f"� *Semester {semester} Selected*\n\n👇 Choose your course:",
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )
        return

    # -----------------------
    # Step 3: Select Course
    # -----------------------
    # -----------------------
    # Step 3: Select Course
    # -----------------------
    if data.startswith("course:"):
        course = data.split(":")[1]
        context.user_data["course"] = course
        
        # Check available content
        year = context.user_data["year"]
        semester = context.user_data["semester"]
        course_data = DATA[year][semester][course]
        
        buttons = []
        # If 'slides' has content, show button
        if course_data.get("slides"):
            buttons.append(InlineKeyboardButton("📄 Slides", callback_data="type:slides"))
        # If 'books' has content, show button
        if course_data.get("books"):
            buttons.append(InlineKeyboardButton("📚 Reference Books", callback_data="type:books"))
        # If 'past' has content, show button
        if course_data.get("past"):
            buttons.append(InlineKeyboardButton("📝 Past Questions", callback_data="type:past"))
        # If 'videos' has content, show button
        if course_data.get("videos"):
            buttons.append(InlineKeyboardButton("🎥 Videos", callback_data="type:videos"))
            
        # Arrange buttons in rows (2 per row)
        keyboard = []
        row = []
        for btn in buttons:
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        # Back button goes to Semester selection
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"sem:{context.user_data['semester']}")])

        await query.edit_message_text(
            f"📘 *{course}*\n\n👇 Choose resource type:",
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )
        return

    # -----------------------
    # Step 4: Select File Type
    # -----------------------
    if data.startswith("type:"):
        file_type = data.split(":")[1]
        context.user_data["file_type"] = file_type
        
        year = context.user_data["year"]
        sem = context.user_data["semester"]
        course = context.user_data["course"]

        files = DATA[year][sem][course].get(file_type, [])

        keyboard = []
        if not files:
             keyboard.append([InlineKeyboardButton("No files found 😕", callback_data="ignore")])
        else:
            for i, f in enumerate(files):
                # Truncate name if too long
                btn_name = (f["name"][:30] + '..') if len(f["name"]) > 30 else f["name"]
                keyboard.append([InlineKeyboardButton(f"⬇️ {btn_name}", callback_data=f"down:{i}")])

        # Back button goes to Course selection
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"course:{course}")])

        type_name_map = {
            "slides": "Slides",
            "past": "Past Questions",
            "books": "Reference Books",
            "videos": "Videos"
        }
        type_name = type_name_map.get(file_type, "Files")
        
        await query.edit_message_text(
            f"📂 *{type_name} for {course}*\n\n👇 Select a file to download:",
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )
        return

    # -----------------------
    # Step 5: Download File
    # -----------------------
    if data.startswith("down:"):
        try:
            index = int(data.split(":")[1])
            year = context.user_data["year"]
            sem = context.user_data["semester"]
            course = context.user_data["course"]
            file_type = context.user_data["file_type"]

            file_info = DATA[year][sem][course][file_type][index]
            name = file_info["name"]
            url = file_info["download_link"]

            await query.message.reply_text(f"🚀 Sending *{name}*...", parse_mode="Markdown")
            
            await context.bot.send_document(chat_id=query.message.chat_id, document=url, filename=name)
        except Exception as e:
            logging.error(f"Error sending file: {e}")
            await query.message.reply_text(f"❌ Error or file too large.\n[Click here to download manually]({url})", parse_mode="Markdown")
        return
    
    if data == "ignore":
        await query.answer("No files available here 😕")
        return

from dotenv import load_dotenv

def main():
    """Run the bot."""
    load_dotenv() # Load variables from .env file
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment variables.")
        return

    application = Application.builder().token(TOKEN).job_queue(None).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()

if __name__ == "__main__":
    main()
