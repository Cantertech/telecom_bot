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
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
import user_manager
import keep_alive

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
    
    # Favorites Button
    keyboard.append([InlineKeyboardButton("⭐ My Favorites", callback_data="fav:list")])

    row = []
    for y in DATA.keys():
        row.append(InlineKeyboardButton(f"🎓 Year {y}", callback_data=f"year:{y}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "👋 *Welcome to Telesa Bot!* 🚀\n\n"
        "🔍 *Smart Search:* Just type the name of a course or file to find it instantly!\n"
        "📚 Access slides, past questions, and books easily.\n"
        "👇 *Select your Year to get started:*"
    )

    # Check if this is a callback (Back button) or a command (/start)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_text,
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
            welcome_text,
            reply_markup=reply_markup, 
            parse_mode="Markdown"
        )
        context.user_data["last_menu_id"] = msg.message_id

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages for Smart Search."""
    query_text = update.message.text.lower()
    
    # Handle greetings
    if query_text in ["hello", "hi", "hey", "start", "menu"]:
        await start(update, context)
        return
    
    # Handle clear
    if query_text == "clear":
        last_menu_id = context.user_data.get("last_menu_id")
        if last_menu_id:
            try:
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=last_menu_id)
            except Exception:
                pass
        return

    if len(query_text) < 3:
        await update.message.reply_text("🔍 Please type at least 3 characters to search.")
        return

    results = []
    
    # Search logic
    for year, year_data in DATA.items():
        for sem, sem_data in year_data.items():
            for course, course_data in sem_data.items():
                # Match Course Name
                if query_text in course.lower():
                    results.append({
                        "type": "course",
                        "name": course,
                        "year": year,
                        "sem": sem,
                        "match": f"📘 {course}"
                    })
                
                # Match File Names
                for cat in ["slides", "past", "books", "videos"]:
                    for file in course_data.get(cat, []):
                        if query_text in file["name"].lower():
                             results.append({
                                "type": "file",
                                "name": file["name"],
                                "link": file["download_link"],
                                "match": f"⬇️ {file['name'][:40]}..."
                            })

    if not results:
        await update.message.reply_text("❌ No results found. Try a different keyword.")
        return

    # Limit results
    results = results[:10]
    
    keyboard = []
    for res in results:
        if res["type"] == "course":
            # Link to open the course
            keyboard.append([InlineKeyboardButton(res["match"], callback_data=f"search_course:{res['year']}:{res['sem']}:{res['name']}")])
        else:
            # Direct download link
            keyboard.append([InlineKeyboardButton(res["match"], url=res["link"])])

    await update.message.reply_text(
        f"🔍 *Search Results for '{query_text}':*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    data = query.data
    try:
        await query.answer()
    except Exception:
        pass # Ignore if query is too old

    # -----------------------
    # Back to Home
    # -----------------------
    if data == "home":
        await start(update, context)
        return

    # -----------------------
    # Favorites List
    # -----------------------
    if data == "fav:list":
        favs = user_manager.get_favorites(query.from_user.id)
        if not favs:
            await query.edit_message_text(
                "⭐ *You have no favorites yet.*\n\nGo to a course and click '⭐ Add to Favorites' to save it here!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="home")]]),
                parse_mode="Markdown"
            )
            return
        
        keyboard = []
        for fav in favs:
            keyboard.append([InlineKeyboardButton(f"📘 {fav['course']}", callback_data=f"course:{fav['course']}")])
            # We need to set context data for these to work directly, but 'course:' handler usually expects them set.
            # Workaround: The 'course:' handler below will need to look up year/sem if missing.
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="home")])
        
        await query.edit_message_text(
            "⭐ *My Favorites*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # -----------------------
    # Toggle Favorite
    # -----------------------
    if data.startswith("fav:toggle:"):
        _, _, year, sem, course = data.split(":")
        user_id = query.from_user.id
        
        if user_manager.is_favorite(user_id, course):
            user_manager.remove_favorite(user_id, course)
            await query.answer("❌ Removed from Favorites")
        else:
            user_manager.add_favorite(user_id, year, sem, course)
            await query.answer("⭐ Added to Favorites")
        
        # Refresh the course view to update the button
        # We trigger the course handler logic again
        data = f"course:{course}"
        # Fall through to course handler...

    # -----------------------
    # Search Result Click (Course)
    # -----------------------
    if data.startswith("search_course:"):
        _, year, sem, course = data.split(":")
        context.user_data["year"] = year
        context.user_data["semester"] = sem
        data = f"course:{course}" # Redirect to standard course handler logic

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
            f"🗓 *Semester {semester} Selected*\n\n👇 Choose your course:",
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )
        return

    # -----------------------
    # Step 3: Select Course
    # -----------------------
    if data.startswith("course:"):
        course = data.split(":")[1]
        context.user_data["course"] = course
        
        # Find year/sem if not in context (e.g. from Favorites or Search)
        if "year" not in context.user_data or "semester" not in context.user_data:
            # Brute force find
            found = False
            for y, y_data in DATA.items():
                for s, s_data in y_data.items():
                    if course in s_data:
                        context.user_data["year"] = y
                        context.user_data["semester"] = s
                        found = True
                        break
                if found: break
        
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

        # Favorites Button
        is_fav = user_manager.is_favorite(query.from_user.id, course)
        fav_text = "❌ Remove Favorite" if is_fav else "⭐ Add to Favorites"
        keyboard.append([InlineKeyboardButton(fav_text, callback_data=f"fav:toggle:{year}:{semester}:{course}")])

        # Back button goes to Semester selection
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"sem:{semester}")])

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
            await query.message.reply_text(f"📂 *File is ready!*\n[👉 Click here to download]({url})", parse_mode="Markdown")
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

    # Start the keep-alive server for Render
    keep_alive.keep_alive()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Add handler for text messages (Smart Search)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling(connect_timeout=30, read_timeout=30, write_timeout=30)

if __name__ == "__main__":
    main()
