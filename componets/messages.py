# -------------------------------------- Tugmalar ---------------------------------------

buttons = {
    "uz": {
        "start": "Assalomu alaykum <b>{name}</b>! Siz avval ro'yxatdan o'tgansiz 😊",
        "choose_lang": "Iltimos, tilni tanlang:",
        "btn_new_chat": "💬 Yangi Chat",
        "btn_stop": "⛔ To'xtatish",
        "btn_continue": "🔄 Davom Ettirish",
        "btn_webapp": "🌐 DeepSeekni ochish",
        "btn_change_lang": "🌍 Tilni almashtirish"
    },
    "ru": {
        "start": "Привет <b>{name}</b>! Вы уже зарегистрированы 😊",
        "choose_lang": "Пожалуйста, выберите язык:",
        "btn_new_chat": "💬 Начать новый чат",
        "btn_stop": "⛔ Остановить",
        "btn_continue": "🔄 Продолжить",
        "btn_webapp": "🌐 Открыть DeepSeek",
        "btn_change_lang": "🌍 Изменить язык"
    },
    "eng": {
        "start": "Hello <b>{name}</b>! You have already registered 😊",
        "choose_lang": "Please choose a language:",
        "btn_new_chat": "💬 Start a New Chat",
        "btn_stop": "⛔ Stop",
        "btn_continue": "🔄 Continue",
        "btn_webapp": "🌐 Open DeepSeek",
        "btn_change_lang": "🌍 Change Language"
    },
    "tr": {
        "start": "Merhaba <b>{name}</b>! Zaten kayıtlısınız 😊",
        "choose_lang": "Lütfen bir dil seçin:",
        "btn_new_chat": "💬 Yeni Sohbet",
        "btn_stop": "⛔ Durdur",
        "btn_continue": "🔄 Devam Et",
        "btn_webapp": "🌐 DeepSeek'i Aç",
        "btn_change_lang": "🌍 Dili Değiştir"
    }
}

#------------------------------------ Xabarlar ------------------------------------------------------

messages = {
    "uz": {
        "choose_lang": "🌍 Iltimos, tilni tanlang:\n\n🇺🇿 O'zbekcha | 🇷🇺 Русский | 🇺🇸 English | 🇹🇷 Türkçe",
        "start": "<b>🤖 AI Chatbot bilan suhbatni boshladingiz!</b>\n\nSavollaringizni yozing.\n\n❌ Chiqish uchun /stop ni yuboring.",
        "stop": "AI Chatbot bilan suhbat yakunlandi.\nQayta boshlash uchun /chat ni yozing.",
        "not_started": "Avval /chat ni yuborib suhbatni boshlang.",
        "limit_reached": "❌ Siz maksimal 20 ta savol berdingiz. Suhbat tugadi.\nQayta boshlash uchun /chat ni yozing.",
        "error": "Xatolik yuz berdi: {}",
        "bot_response": "<b>Gemini:</b>\n\n{}",
        "thinking": "⌛ O'ylamoqda...",
        "time_waiter": "⏳Iltimos, biroz kuting va qayta urinib ko'ring!",
        "start_command": "<b> 🤖 AI Chatbot bilan suhbatni boshlash uchun /chat buyrug'ini yuboring yoki pastdagi tugmalardan foydalaning. \n\n ❌ Chiqish uchun /stop ni yuboring.</b>",
        "voice_processing": "🎤 Ovozli xabarni qayta ishlayman...",
        "voice_error": "❌ Ovozli xabarni qayta ishlashda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
        "voice_recognized": "🎯 Sizning xabaringiz: <i>{text}</i>",
        "time_waiter": "Server hozir band kutish vaqti: {minute}"
    },
    "ru": {
        "choose_lang": "🌍 Пожалуйста, выберите язык:\n\n🇺🇿 O'zbekcha | 🇷🇺 Русский | 🇺🇸 English | 🇹🇷 Türkçe",
        "start": "<b>🤖 Вы начали чат с AI Chatbot!</b>\n\nЗадайте свой вопрос.\n\n❌ Чтобы выйти, отправьте /stop.",
        "stop": "Чат с AI Chatbot завершен.\nЧтобы начать заново, отправьте /chat.",
        "not_started": "Сначала отправьте /chat, чтобы начать чат.",
        "limit_reached": "❌ Вы задали 20 вопросов. Чат завершен.\nЧтобы начать заново, отправьте /chat.",
        "error": "Произошла ошибка: {}",
        "bot_response": "<b>Gemini:</b>\n\n{}",
        "thinking": "⌛ Думаю...",
        "time_waiter": "⏳Пожалуйста, подождите немного и повторите попытку!",
        "start_command": "<b> 🤖 Отправьте команду /chat или воспользуйтесь кнопками ниже, чтобы начать разговор с AI Chatbot. \n\n ❌ Отправьте /stop для выхода.</b>",
        "voice_processing": "🎤 Обрабатываю голосовое сообщение...",
        "voice_error": "❌ Ошибка при обработке голосового сообщения. Пожалуйста, попробуйте снова.",
        "voice_recognized": "🎯 Ваше сообщение: <i>{text}</i>",
        "time_waiter": "Server hozir band kutish vaqti: {minute}"

    },
    "eng": {
        "choose_lang": "🌍 Please choose a language:\n\n🇺🇿 O'zbekcha | 🇷🇺 Русский | 🇺🇸 English | 🇹🇷 Türkçe",
        "start": "<b>🤖 You started a chat with AI Chatbot!</b>\n\nAsk your questions.\n\n❌ To exit, send /stop.",
        "stop": "AI Chatbot session ended.\nTo restart, send /chat.",
        "not_started": "Please send /chat to start a conversation.",
        "limit_reached": "❌ You have reached the maximum of 20 questions. Chat ended.\nTo restart, send /chat.",
        "error": "An error occurred: {}",
        "bot_response": "<b>Gemini:</b>\n\n{}",
        "thinking": "⌛ Thinking...",
        "time_waiter": "⏳Please wait a while and try again!",
        "start_command": "<b> 🤖 Send the /chat command or use the buttons below to start a conversation with the AI Chatbot. \n\n ❌ Send /stop to exit.</b>",
        "voice_processing": "🎤 Processing voice message...",
        "voice_error": "❌ Error processing voice message. Please try again.",
        "voice_recognized": "🎯 Your message: <i>{text}</i>",
        "time_waiter": "Server hozir band kutish vaqti: {minute}"
    },
    "tr": {
        "choose_lang": "🌍 Lütfen bir dil seçin:\n\n🇺🇿 O'zbekcha | 🇷🇺 Русский | 🇺🇸 English | 🇹🇷 Türkçe",
        "start": "<b>🤖 AI Chatbot ile sohbete başladınız!</b>\n\nSorularınızı sorun.\n\n❌ Çıkmak için /stop gönderin.",
        "stop": "AI Chatbot oturumu sonlandı.\nYeniden başlatmak için /chat gönderin.",
        "not_started": "Lütfen sohbete başlamak için /chat gönderin.",
        "limit_reached": "❌ Maksimum 20 soru limitine ulaştınız. Sohbet sonlandı.\nYeniden başlatmak için /chat gönderin.",
        "error": "Bir hata oluştu: {}",
        "bot_response": "<b>Gemini:</b>\n\n{}",
        "thinking": "⌛ Düşünüyor...",
        "time_waiter": "⏳Lütfen biraz bekleyin ve tekrar deneyin!",
        "start_command": "<b> 🤖 AI Chatbot ile sohbete başlamak için /chat komutunu gönderin veya aşağıdaki düğmeleri kullanın. \n\n ❌ Çıkmak için /stop gönderin.</b>",
        "voice_processing": "🎤 Ses mesajı işleniyor...",
        "voice_error": "❌ Ses mesajı işlenirken hata oluştu. Lütfen tekrar deneyin.",
        "voice_recognized": "🎯 Mesajınız: <i>{text}</i>",
        "time_waiter": "Server hozir band kutish vaqti: {minute}"
    }
}