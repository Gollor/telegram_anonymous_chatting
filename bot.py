import logging
import json
import os
import time

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Dispatcher, JobQueue
from telegram.ext.dispatcher import run_async
from telegram import Update, Message, Bot

TOKEN = os.environ["TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

class AnonBot:
    def __init__(self):
        if os.path.exists('data.json'):
            self.data = json.load(open('data.json', 'r'))
            self.data_from = {}
            self.banned = {}
            for gamek, gamev in self.data.items():
                self.data_from[gamek] = {}
                for k, v in gamev.items():
                    self.data_from[gamek][v] = k
        else:
            self.data = {}
            self.data_from = {}
        self.updater = Updater(TOKEN)
        dp: Dispatcher = self.updater.dispatcher
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("register", self.register, pass_args=True))
        dp.add_handler(CommandHandler("unregister", self.unregister, pass_args=True))
        dp.add_handler(CommandHandler("message", self.message, pass_args=True))
        dp.add_handler(CommandHandler("new_game", self.new_game, pass_args=True))
        dp.add_handler(CommandHandler("delete_game", self.delete_game, pass_args=True))
        dp.add_handler(CommandHandler("ban", self.ban, pass_args=True))
        dp.add_handler(CommandHandler("unban", self.unban, pass_args=True))
        dp.add_handler(CommandHandler("list", self.list))
        self.job_queue = self.updater.job_queue

    def run(self):
        self.updater.start_polling()
        self.updater.idle()

    def new_game(self, bot: Bot, update: Update, args):
        msg: Message = update.message
        if msg.from_user.id != ADMIN_ID:
            msg.reply_text('Sorry. You are not authorized.')
        elif args[0] in self.data:
            msg.reply_text(f'Game {args[0]} is already present.')
        else:
            self._new_game(args[0])
            msg.reply_text(f'Game {args[0]} created!')

    def delete_game(self, bot: Bot, update: Update, args):
        msg: Message = update.message
        if msg.chat_id != ADMIN_ID:
            msg.reply_text('Sorry. You are not authorized.')
        elif args[0] in self.data:
            self._delete_game(args[0])
            msg.reply_text(f'Game {args[0]} deleted!')
        else:
            msg.reply_text(f'Game {args[0]} is not present.')

    def _new_game(self, game):
        self.data[game] = {}
        self.data_from[game] = {}
        json.dump(self.data, open('data.json', 'w'))

    def _delete_game(self, game):
        del self.data[game]
        del self.data_from[game]
        json.dump(self.data, open('data.json', 'w'))

    def start(self, bot: Bot, update: Update):
        msg: Message = update.message
        msg.reply_text('Hello! There are next commands:\n'
                       '/list - show people\n'
                       '/message {game} {user} {delay in minutes} {text} - send message\n'
                       '/register {game} {user} - register yourself\n'
                       '/unregister {game} - unregister yourself\n'
                       '/new_game {game} - New game. Responds only to admin\n'
                       '/delete_game {game} - Deletes game. Responds only to admin\n'
                       '/ban {game} {user} - Bans user from all games. Responds only to admin\n'
                       '/unban {user} - Unbans user. Responds only to admin')

    def unregister(self, bot: Bot, update: Update, args):
        msg: Message = update.message
        game = args[0]
        if game not in self.data:
            msg.reply_text(f'Sorry. Game {game} is not present.')
        elif msg.chat_id not in self.data_from[game]:
            msg.reply_text(f'Sorry. You are not registered.')
        else:
            user = self.data_from[game][msg.chat_id]
            del self.data[game][user]
            del self.data_from[game][msg.chat_id]
            json.dump(self.data, open('data.json', 'w'))
            msg.reply_text(f'Bye!')

    def register(self, bot: Bot, update: Update, args):
        msg: Message = update.message
        if args[0] not in self.data:
            msg.reply_text(f'Sorry. Game {args[0]} is not present.')
        elif args[1] in self.data[args[0]]:
            msg.reply_text(f'Sorry. User {args[1]} is already present.')
        elif msg.chat_id in self.data_from[args[0]]:
            msg.reply_text(f'Sorry. You are already registered.')
        else:
            self.data[args[0]][args[1]] = msg.chat_id
            self.data_from[args[0]][msg.chat_id] = args[1]
            json.dump(self.data, open('data.json', 'w'))
            msg.reply_text(f'Hello, {args[1]}!')

    def list(self, bot: Bot, update: Update):
        msg: Message = update.message
        items = [f'banned: {" ".join(self.banned.keys())}']
        for game, gdata in self.data.items():
            items += [f'{game}: {" ".join(gdata.keys())}']
        msg.reply_text('\n'.join(items))

    def ban(self, bot: Bot, update: Update, args):
        game = args[0]
        user = args[1]
        msg: Message = update.message
        if msg.chat_id != ADMIN_ID:
            msg.reply_text('Sorry. You are not authorized.')
        elif game not in self.data:
            msg.reply_text(f'Sorry. There is no game {game}.')
        elif user not in self.data[game]:
            msg.reply_text(f'Sorry. There is no user {user}.')
        else:
            self.banned[user] = self.data[game][user]
            msg.reply_text(f'User {user} banned...')

    def unban(self, bot: Bot, update: Update, args):
        user = args[0]
        msg: Message = update.message
        if msg.chat_id in self.banned.values():
            msg.reply_text(f'Sorry. You are banned...')
        elif msg.chat_id != ADMIN_ID:
            msg.reply_text('Sorry. You are not authorized.')
        elif user not in self.banned[user]:
            msg.reply_text(f'Sorry. There is no user {user}.')
        else:
            del self.banned[user]
            msg.reply_text(f'User {user} unblocked!')

    @run_async
    def message(self, bot: Bot, update: Update, args):
        game = args[0]
        user = args[1]
        delay = int(args[2])
        msg: Message = update.message
        if game not in self.data:
            msg.reply_text(f'Sorry. There is no game {game}.')
        elif msg.chat_id not in self.data_from[game]:
            msg.reply_text(f'Sorry. You need to register to send messages.')
        elif user not in self.data[game]:
            msg.reply_text(f'Sorry. There is no user {user}.')
        else:
            user_from = self.data_from[game][msg.chat_id]
            if delay > 0:
                msg.reply_text(f'Message recorded.')
            time.sleep(60 * delay)
            message = ' '.join(args[3:])
            text = f'Message from {user_from} in {game}: {message}'
            self.updater.bot.send_message(chat_id=self.data[game][user], text=text)
            msg.reply_text(f'Message sent.')


if __name__ == '__main__':
    AnonBot().run()
