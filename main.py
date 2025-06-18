import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import datetime
import requests
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class MistralAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1/chat/completions"

    async def generate_response(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "mistral-tiny",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Mistral API Error: {e}")
            return "⚠️ Ошибка при обработке запроса. Попробуйте позже."


class TelegramBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.mistral = MistralAPI(api_key="dihA4RmtkbZcEvOwdTRpD0xlNLcgbQS5")
        self.db = Database("sqlite:///users.db")

        # Регистрация обработчиков в правильном порядке
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("subscribe", self.subscribe))
        self.application.add_handler(CommandHandler("support", self.support))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    def get_back_button(self):
        """Возвращает кнопку 'Назад' для клавиатуры"""
        return [InlineKeyboardButton("🔙 Назад", callback_data='start')]

    async def start(self, update: Update, context: CallbackContext):
        user = update.effective_user
        user_id = user.id

        if not self.db.user_exists(user_id):
            self.db.add_user(
                user_id,
                username=user.username,
                free_requests_left=10,
                last_request_date=datetime.date.today(),
                is_subscribed=False
            )
            welcome_msg = (
                f"👋 Привет, {user.first_name}!\n\n"
                "Я - чат-бот с нейросетью Mistral AI.\n"
                "🔹 Тебе доступно 10 бесплатных запросов в день\n"
                "🔹 Безлимитный доступ по подписке (/subscribe)\n\n"
                "Просто напиши мне свой вопрос!"
            )
        else:
            user_data = self.db.get_user(user_id)
            requests_left = user_data.free_requests_left
            welcome_msg = (
                f"🔄 С возвращением, {user.first_name}!\n\n"
                f"🔹 Осталось запросов сегодня: {requests_left}\n"
                f"🔹 Статус подписки: {'✅ Активна' if user_data.is_subscribed else '❌ Неактивна'}\n\n"
                f"🔹Просто напиши мне свой вопрос!\n\n"
                "Нужна помощь? /help"
            )

        keyboard = [
            [InlineKeyboardButton("💳 Оформить подписку", callback_data='subscribe')],
            [InlineKeyboardButton("🆘 Техподдержка", callback_data='support')],
            [InlineKeyboardButton("💖 Поддержать проект", callback_data='donate')],
            self.get_back_button()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.send_or_edit_message(update, welcome_msg, reply_markup)

    async def help(self, update: Update, context: CallbackContext):
        help_text = (
            "📚 Справка по боту:\n\n"
            "🔹 /start - Главное меню\n"
            "🔹 /subscribe - Информация о подписке\n"
            "🔹 /support - Связь с техподдержкой\n\n"
            "❓ Бесплатные запросы:\n"
            "- 10 запросов в день\n"
            "- Сбрасываются в 00:00\n\n"
            "💎 Подписка дает:\n"
            "- Неограниченные запросы\n"
            "- Приоритетную обработку\n\n"
            "💖 Поддержать проект можно через /donate"
        )

        reply_markup = InlineKeyboardMarkup([self.get_back_button()])
        await self.send_or_edit_message(update, help_text, reply_markup)

    async def subscribe(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)

        if user.is_subscribed:
            expiry_date = user.subscription_expiry
            reply_markup = InlineKeyboardMarkup([self.get_back_button()])
            await self.send_or_edit_message(
                update,
                f"✅ Ваша подписка уже активна до {expiry_date}!",
                reply_markup
            )
            return

        keyboard = [
            [InlineKeyboardButton("💰 Месяц - 199 руб.", callback_data='sub_month')],
            [InlineKeyboardButton("💎 Год - 1599 руб. (экономия 33%)", callback_data='sub_year')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel')],
            self.get_back_button()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.send_or_edit_message(
            update,
            "🎟 Выберите тип подписки:",
            reply_markup
        )

    async def support(self, update: Update, context: CallbackContext):
        support_msg = (
            "🛠 Техническая поддержка:\n\n"
            "По всем вопросам пишите @Mistral_support\n\n"
            "Мы отвечаем в течение 24 часов."
        )
        reply_markup = InlineKeyboardMarkup([self.get_back_button()])
        await self.send_or_edit_message(update, support_msg, reply_markup)

    async def send_or_edit_message(self, update: Update, text: str, reply_markup=None):
        """Универсальный метод для отправки/редактирования сообщений"""
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)

    async def handle_message(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        message_text = update.message.text

        # Проверка лимитов
        if not user.is_subscribed:
            if user.free_requests_left <= 0:
                keyboard = [
                    [InlineKeyboardButton("💳 Оформить подписку", callback_data='subscribe')],
                    self.get_back_button()
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    "🚫 Лимит запросов исчерпан!\n\n"
                    "Оформите подписку для неограниченного доступа:",
                    reply_markup=reply_markup
                )
                return
            self.db.update_user(user_id, {'free_requests_left': user.free_requests_left - 1})

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            response = await self.mistral.generate_response(message_text)
            response = response[:4000] + "..." if len(response) > 4000 else response

            # Добавляем кнопку "Назад" к ответу нейросети
            reply_markup = InlineKeyboardMarkup([self.get_back_button()])
            await update.message.reply_text(response, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error: {e}")
            reply_markup = InlineKeyboardMarkup([self.get_back_button()])
            await update.message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.", reply_markup=reply_markup)

    async def button_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()  # Важно для подтверждения получения callback

        user_id = query.from_user.id
        data = query.data

        logger.info(f"Received callback: {data} from user {user_id}")

        if data == 'subscribe':
            await self.subscribe(update, context)
        elif data == 'support':
            await self.support(update, context)
        elif data == 'donate':
            keyboard = [
                [InlineKeyboardButton("BTC", callback_data='donate_btc')],
                [InlineKeyboardButton("ETH", callback_data='donate_eth')],
                [InlineKeyboardButton("ЮMoney", callback_data='donate_ym')],
                [InlineKeyboardButton("USDT", callback_data='donate_usdt')],
                self.get_back_button()
            ]
            await query.edit_message_text(
                "💖 Поддержать проект:\n\n"
                "Выберите способ оплаты:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif data == 'donate_btc':
            await query.edit_message_text(
                "BTC: bc1qpd5993v84uzn54kwygvw2nk6rdun2997326s4n\n\n"
                "Спасибо за вашу поддержку! 🙏",
                reply_markup=InlineKeyboardMarkup([self.get_back_button()])
            )
        elif data == 'donate_eth':
            await query.edit_message_text(
                "ETH: 0x41C220fFE11d76B7Fd48F712B4B06A1955622Dd3\n\n"
                "Спасибо за вашу поддержку! 🙏",
                reply_markup=InlineKeyboardMarkup([self.get_back_button()])
            )
        elif data == 'donate_ym':
            await query.edit_message_text(
                "ЮMoney: 4100116764799228\n\n"
                "Спасибо за вашу поддержку! 🙏",
                reply_markup=InlineKeyboardMarkup([self.get_back_button()])
            )
        elif data == 'donate_usdt':
            await query.edit_message_text(
                "USDT(trx20): TLqAx9wR9wYnEWeBxchfJQtYPjP2D6St3E\n\n"
                "Спасибо за вашу поддержку! 🙏",
                reply_markup=InlineKeyboardMarkup([self.get_back_button()])
            )
        elif data.startswith('sub_'):
            period = data.split('_')[1]
            days = 30 if period == 'month' else 365
            expiry_date = datetime.date.today() + datetime.timedelta(days=days)

            self.db.update_user(user_id, {
                'is_subscribed': True,
                'subscription_expiry': expiry_date,
                'free_requests_left': 999
            })

            await query.edit_message_text(
                f"✅ Подписка активирована до {expiry_date}!\n\n"
                "Теперь у вас неограниченные запросы!",
                reply_markup=InlineKeyboardMarkup([self.get_back_button()])
            )
        elif data == 'cancel':
            await query.edit_message_text(
                "❌ Операция отменена",
                reply_markup=InlineKeyboardMarkup([self.get_back_button()])
            )
        elif data == 'start':
            await self.start(update, context)

    def run(self):
        self.application.run_polling()


if __name__ == '__main__':
    bot = TelegramBot("7838287573:AAGU-gNBWn6bXsc2sLyJ7B7d7j6kkVjOY6Q")
    bot.run()