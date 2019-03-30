# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import uno

import telegram
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from telegram.error import TelegramError, Unauthorized
import logging

import sys, os

# https://github.com/CaKEandLies/Telegram_Cthulhu/blob/master/cthulhu_game_bot.py
# https://docs.google.com/document/d/11egPOVQx0rk9QYn6_hmUOVzY_TzZdpVGSUPND0AF_Z4/edit
# https://github.com/python-telegram-bot/python-telegram-bot/wiki/Webhooks#heroku

with open("api_key.txt", 'r') as f:
    TOKEN = f.read().rstrip()

MIN_PLAYERS = 2
THRESHOLD_PLAYERS = 10
PORT = int(os.environ.get('PORT', '8443'))


def static_handler(command):
    """
    Given a string command, returns a CommandHandler for that string that
    responds to messages with the content of static_responses/[command].txt
    Throws IOError if file does not exist.
    """

    text = open("static_responses/{}.txt".format(command), "r").read()

    return CommandHandler(command,
        lambda bot, update: bot.send_message(chat_id=update.message.chat.id, text=text))


def reset_chat_data(chat_data):
    chat_data["is_game_pending"] = False
    chat_data["pending_players"] = {}
    chat_data["game"] = None


def newgame_handler(bot, update, chat_data):
    """
    Create a new game of Uno.
    """
    game = chat_data.get("game")
    chat_id = update.message.chat.id

    if game is None and not chat_data.get("is_game_pending", False):
        reset_chat_data(chat_data)
        chat_data["is_game_pending"] = True
        text = open("static_responses/new_game.txt", "r").read()
    elif game is not None:
        text = open("static_responses/game_ongoing.txt", "r").read()
    elif chat_data.get("is_game_pending", False):
        text = open("static_responses/game_pending.txt", "r").read()
    else:
        text = "Something has gone horribly wrong!"

    bot.send_message(chat_id=chat_id, text=text)


def is_nickname_valid(name, user_id, chat_data):
    if len(name) < 3 or len(name) > 15:
        return False

    if user_id in chat_data.get("pending_players", {}):
        if name.lower() == chat_data["pending_players"][user_id].lower():
            return True

    for id, user_name in chat_data.get("pending_players", {}).items():
        if name.lower() == user_name.lower():
            return False

    try:
        float(name)
        return False
    except ValueError as e:
        return True


def join_handler(bot, update, chat_data, args):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id

    if not chat_data.get("is_game_pending", False):
        text = open("static_responses/join_game_not_pending.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    if args:
        nickname = " ".join(args)
    else:
        nickname = update.message.from_user.first_name

    if is_nickname_valid(nickname, user_id, chat_data):
        chat_data["pending_players"][user_id] = nickname
        bot.send_message(chat_id=update.message.chat_id,
                         text="Joined with nickname %s!" % nickname)
        bot.send_message(chat_id=update.message.chat_id,
                         text="Current player count: %d" % len(chat_data.get("pending_players", {})))
    else:
        text = open("static_responses/invalid_nickname.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)


def leave_handler(bot, update, chat_data):
    """
    Forces a user to leave the current game.
    """
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    if not chat_data.get("is_game_pending", False):
        text = open("static_responses/leave_game_not_pending_failure.txt", "r").read()
    elif user_id not in chat_data.get("pending_players", {}):
        text = open("static_responses/leave_id_missing_failure.txt", "r").read()
    else:
        text = "You have left the current game."
        del chat_data["pending_players"][update.message.from_user.id]

    bot.send_message(chat_id=chat_id, text=text)


def listplayers_handler(bot, update, chat_data):
    chat_id = update.message.chat_id
    text = "List of players: \n"
    game = chat_data.get("game")

    if game is None or not chat_data.get("is_game_pending", False):
        for user_id, name in chat_data.get("pending_players", {}).items():
            text += name + "\n"
    else:
        text = open("static_responses/listplayers_failure.txt", "r").read()

    bot.send_message(chat_id=chat_id, text=text)


def feedback_handler(bot, update, args):
    """
    Store feedback from users in a text file.
    """
    if args and len(args) > 0:
        feedback = open("feedback.txt\n", "a")
        feedback.write(update.message.from_user.first_name + "\n")
        # Records User ID so that if feature is implemented, can message them
        # about it.
        feedback.write(str(update.message.from_user.id) + "\n")
        feedback.write(" ".join(args) + "\n")
        feedback.close()
        bot.send_message(chat_id=update.message.chat_id,
                         text="Thanks for the feedback!")
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Format: /feedback [feedback]")


def startgame_handler(bot, update, chat_data):
    chat_id = update.message.chat_id

    if not chat_data.get("is_game_pending", False):
        text = open("static_responses/start_game_not_pending.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return
    if len(chat_data.get("pending_players", {})) < MIN_PLAYERS:
        text = open("static_responses/start_game_min_threshold.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    # Try to message all users.
    try:
        for user_id, nickname in chat_data.get("pending_players", {}).items():
            bot.send_message(chat_id=user_id, text="Trying to start game!")
    except Unauthorized as u:
        text = open("static_responses/start_game_failure.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    chat_data["is_game_pending"] = False
    game = uno.Game(bot, chat_id, chat_data.get("pending_players", {}))
    chat_data["game"] = game

    text = open("static_responses/start_game.txt", "r").read()
    bot.send_message(chat_id=chat_id, text=text)
    bot.send_message(chat_id=chat_id, text=game.get_state())

    for user_id, nickname in chat_data.get("pending_players", {}).items():
        bot.send_message(chat_id=user_id, text=game.get_player(user_id).get_formatted_hand())


def endgame_handler(bot, update, chat_data):
    chat_id = update.message.chat.id
    game = chat_data.get("game", None)

    if chat_data.get("is_game_pending", False):
        chat_data["is_game_pending"] = False
        text = open("static_responses/end_game.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    if game is None:
        text = open("static_responses/game_dne_failure.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    reset_chat_data(chat_data)
    text = open("static_responses/end_game.txt", "r").read()
    bot.send_message(chat_id=chat_id, text=text)


def draw_handler(bot, update, chat_data):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    game = chat_data.get("game", None)

    if game is None:
        text = open("static_responses/game_dne_failure.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    game.draw_and_continue(user_id)
    bot.send_message(chat_id=chat_id, text=game.get_state())
    for id in game.get_players().keys():
        bot.send_message(chat_id=id, text=game.get_player(id).get_formatted_hand())


def play_handler(bot, update, chat_data, args):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    game = chat_data.get("game", None)

    if len(args) != 1:
        bot.send_message(chat_id=chat_id, text="Usage: /play card_id")
        return

    if game is None:
        text = open("static_responses/game_dne_failure.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    result = game.play_card(user_id, int(" ".join(args)))

    if result != "":
        bot.send_message(chat_id=chat_id, text="The next player has been skipped!\n\n" + result)
        return

    player = game.get_player(user_id)

    if player is None:
        bot.send_message(chat_id=chat_id, text="Something has gone horribly wrong!")
        return

    if len(player.get_hand()) == 1:
        game.set_uno_pending(True)
        bot.send_message(chat_id=chat_id,
                         reply_markup=telegram.InlineKeyboardMarkup([telegram.InlineKeyboardButton("Uno")]))

    winner = game.check_for_win()
    if winner is not None:
        bot.send_message(chat_id=chat_id, text=winner + " has won!")
        endgame_handler(bot, update, chat_data)
        return

    if not game.is_uno_pending:
        game.next_turn(1)
        bot.send_message(chat_id=chat_id, text=game.get_state())
        for id in game.get_players().keys():
            bot.send_message(chat_id=id, text=game.get_player(id).get_formatted_hand())


def uno_button(bot, update, chat_data):
    query = update.callback_query
    chat_id = update.message.chat.id
    user_id = query.from_user
    game = chat_data["game"]

    if game is None:
        text = open("static_responses/game_dne_failure.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    if game.is_uno_pending():
        game.check_uno_caller(user_id)
        game.next_turn(1)
        bot.send_message(chat_id=chat_id, text=game.get_state())
        for id in game.get_players().keys():
            bot.send_message(chat_id=id, text=game.get_player(id).get_formatted_hand())


def wild_handler(bot, update, chat_data, args):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    game = chat_data.get("game", None)

    if game is None:
        text = open("static_responses/game_dne_failure.txt", "r").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    game.set_wild_color(user_id, " ".join(args))
    game.next_turn(1)


def handle_error(bot, update, error):
    try:
        raise error
    except TelegramError:
        logging.getLogger(__name__).warning('Telegram Error! %s caused by this update: %s', error, update)


if __name__ == "__main__":
    # Set up the bot

    bot = telegram.Bot(token=TOKEN)
    updater = Updater(token=TOKEN)
    dispatcher = updater.dispatcher

    # Static command handlers

    static_commands = ["start", "rules", "help"]
    for c in static_commands:
        dispatcher.add_handler(static_handler(c))

    # Main command handlers

    commands = [("feedback", 0), ("newgame", 1), ("join", 2), ("leave", 1),
                ("listplayers", 1), ("startgame", 1), ("endgame", 1), ("draw", 1),
                ("play", 2), ("wild", 2)]
    for c in commands:
        func = locals()[c[0] + "_handler"]
        if c[1] == 0:
            dispatcher.add_handler(CommandHandler(c[0], func, pass_args=True))
        elif c[1] == 1:
            dispatcher.add_handler(CommandHandler(c[0], func, pass_chat_data=True))
        elif c[1] == 2:
            dispatcher.add_handler(CommandHandler(c[0], func, pass_chat_data=True, pass_args=True))

    # Uno button handler

    dispatcher.add_handler(CallbackQueryHandler(uno_button))

    # Error handlers

    dispatcher.add_error_handler(handle_error)

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO, filename='logging.txt', filemode='a')

    # Begin the updater.

    updater.start_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN)
    updater.bot.set_webhook("https://la-uno-bot.herokuapp.com/" + TOKEN)

    #updater.start_polling()
    updater.idle()
