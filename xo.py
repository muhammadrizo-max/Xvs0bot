import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command

TOKEN = "8263929871:AAGrNR_x-9xuAWZQk7qq0a4mPVPnDFUjmes"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# -------- Foydalanuvchi session va reyting ---------
sessions = {}  # user_id: game session
waiting_for_friend = []  # do'st bilan o'yin queue
SCORE_FILE = "score.json"

if os.path.exists(SCORE_FILE):
    with open(SCORE_FILE, "r") as f:
        score = json.load(f)
else:
    score = {"users": {}}

# ----------- Inline tugmalar ------------------------
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="Kataklar hajmini o'zgartirish", callback_data="change_size"),
        InlineKeyboardButton(text="Mening reytingim", callback_data="my_rating"),
        InlineKeyboardButton(text="Orqaga", callback_data="back")
    )
    return kb.as_markup()

def choose_mode():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="AIga qarshi", callback_data="mode_ai"),
        InlineKeyboardButton(text="Do‘st bilan o‘ynash", callback_data="mode_friend")
    )
    return kb.as_markup()

def make_board_markup(session):
    kb = InlineKeyboardBuilder()
    size = session["size"]
    for i in range(size*size):
        cell = session["board"][i] if session["board"][i] != "" else "⬜"
        kb.button(text=cell, callback_data=f"cell_{i}")
        if (i+1)%size == 0:
            kb.row()
    return kb.as_markup(resize_keyboard=True)

# ----------- Session yaratish ---------------------
def create_session(user_id, size=3):
    sessions[user_id] = {
        "board": [""]*(size*size),
        "size": size,
        "turn": "X",  # X har doim boshlaydi
        "mode": None,  # ai yoki friend
        "friend_id": None
    }

# ----------- G'oliblik va durrang -----------------
def check_winner(board, player, size):
    lines = []

    for i in range(size):
        lines.append([i*size+j for j in range(size)])  # qator
        lines.append([i+j*size for j in range(size)])  # ustun
    lines.append([i*(size+1) for i in range(size)])  # diagonal \
    lines.append([(i+1)*(size-1) for i in range(size)])  # diagonal /

    for line in lines:
        if all(board[i]==player for i in line):
            return True
    return False

def is_draw(board):
    return all(cell != "" for cell in board)

# ----------- Reytingni saqlash --------------------
def save_score():
    with open(SCORE_FILE, "w") as f:
        json.dump(score, f)

def update_user_score(user_id, username):
    if str(user_id) not in score["users"]:
        score["users"][str(user_id)] = {"username": username, "score": 0}
    score["users"][str(user_id)]["score"] += 1
    save_score()

def get_top10():
    users = list(score["users"].values())
    users.sort(key=lambda x: x["score"], reverse=True)
    return users[:10]

# ----------- Start va menyu ------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    create_session(message.from_user.id)
    await message.answer("X vs 0 o'yiniga xush kelibsiz!", reply_markup=main_menu())

# ----------- Callback handler ----------------------
@dp.callback_query()
async def callbacks(cb: types.CallbackQuery):
    user_id = cb.from_user.id
    data = cb.data
    session = sessions.get(user_id)
    username = cb.from_user.username or cb.from_user.first_name

    # --- Kataklar hajmini o'zgartirish ---
    if data == "change_size":
        await cb.message.answer("Kataklar hajmi (3-5) ni tanlang:")
        return

    # --- Reyting ---
    elif data == "my_rating":
        top = get_top10()
        msg = "🏆 Top 10 Reyting:\n"
        for idx, u in enumerate(top, start=1):
            msg += f"{idx}. {u['username']} - {u['score']}\n"
        await cb.message.answer(msg)
        return

    # --- Orqaga ---
    elif data == "back":
        await cb.message.edit_text("Asosiy menyu", reply_markup=main_menu())
        return

    # --- AI yoki Friend tanlash ---
    elif data == "mode_ai":
        session["mode"] = "ai"
        await cb.message.edit_text("O‘yin AIga qarshi boshlanadi:", reply_markup=make_board_markup(session))
        return
    elif data == "mode_friend":
        session["mode"] = "friend"
        waiting_for_friend.append(user_id)
        if len(waiting_for_friend) > 1:
            friend_id = None
            for uid in waiting_for_friend:
                if uid != user_id:
                    friend_id = uid
                    break
            if friend_id:
                # bog'lash
                session["friend_id"] = friend_id
                sessions[friend_id]["friend_id"] = user_id
                waiting_for_friend.remove(user_id)
                waiting_for_friend.remove(friend_id)
                # ikkala userga xabar
                await bot.send_message(user_id, "O‘yin do‘st bilan boshlanadi:", reply_markup=make_board_markup(session))
                await bot.send_message(friend_id, "O‘yin do‘st bilan boshlanadi:", reply_markup=make_board_markup(sessions[friend_id]))
        else:
            await cb.message.answer("Do‘stingizni kuting...")
        return

    # --- Katakni bosish ---
    elif data.startswith("cell_"):
        idx = int(data.split("_")[1])
        if session["board"][idx] != "":
            return

        # Navbatni aniqlash
        if session["mode"] == "ai":
            session["board"][idx] = "X"
            # tekshirish
            if check_winner(session["board"], "X", session["size"]):
                update_user_score(user_id, username)
                await cb.message.edit_text("Siz yutdingiz! 🎉", reply_markup=make_board_markup(session))
                create_session(user_id, session["size"])
                return
            elif is_draw(session["board"]):
                await cb.message.edit_text("Durrang! 🤝", reply_markup=make_board_markup(session))
                create_session(user_id, session["size"])
                return
            # AI yurishi
            empty = [i for i, v in enumerate(session["board"]) if v==""]
            if empty:
                move = random.choice(empty)
                session["board"][move] = "0"
            await cb.message.edit_text("O‘yin davom etmoqda:", reply_markup=make_board_markup(session))
            return

        elif session["mode"] == "friend":
            # ikki foydalanuvchi uchun bir xil kataklar
            friend_id = session["friend_id"]
            session["board"][idx] = session["turn"]
            if friend_id:
                sessions[friend_id]["board"][idx] = session["turn"]

            # tekshirish
            if check_winner(session["board"], session["turn"], session["size"]):
                await cb.message.edit_text(f"{session['turn']} yutdi! 🎉", reply_markup=make_board_markup(session))
                if session["turn"] == "X":
                    update_user_score(user_id, username)
                else:
                    update_user_score(friend_id, sessions[friend_id]["username"])
                # reset
                create_session(user_id, session["size"])
                create_session(friend_id, sessions[friend_id]["size"])
                return
            elif is_draw(session["board"]):
                await cb.message.edit_text("Durrang! 🤝", reply_markup=make_board_markup(session))
                if friend_id:
                    create_session(friend_id, sessions[friend_id]["size"])
                create_session(user_id, session["size"])
                return
            # navbatni o‘zgartirish
            session["turn"] = "0" if session["turn"]=="X" else "X"
            if friend_id:
                sessions[friend_id]["turn"] = session["turn"]
                await bot.edit_message_text(chat_id=friend_id, message_id=cb.message.message_id,
                                            text="O‘yin davom etmoqda:", reply_markup=make_board_markup(sessions[friend_id]))
            await cb.message.edit_text("O‘yin davom etmoqda:", reply_markup=make_board_markup(session))
            return

# ----------- Run bot -----------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    import asyncio
    asyncio.run(dp.start_polling(bot))
