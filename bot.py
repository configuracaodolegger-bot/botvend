import os
import asyncio
import requests
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler

# Variáveis de ambiente
TOKEN = os.environ.get("BOT_TOKEN")
LINK_GRUPO = os.environ.get("GROUP_LINK")
EXPFY_PUBLIC_KEY = os.environ.get("EXPFY_PUBLIC_KEY")
EXPFY_SECRET_KEY = os.environ.get("EXPFY_SECRET_KEY")
VALOR = float(os.environ.get("VALOR", 29.90))
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_KEY = os.environ.get("WEBHOOK_KEY", "minha_chave_123")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}")

usuarios = {}
tg_app = Application.builder().token(TOKEN).build()


def gerar_pix(user_id: int, valor: float):
    payload = {
        "amount": valor,
        "description": "Acesso ao Grupo VIP",
        "customer": {"name": f"User {user_id}", "document": "000.000.000-00"},
        "external_id": str(user_id),
        "callback_url": f"{WEBHOOK_URL}/expfy_webhook"
    }
    headers = {
        "X-Public-Key": EXPFY_PUBLIC_KEY,
        "X-Secret-Key": EXPFY_SECRET_KEY,
        "Content-Type": "application/json"
    }
    r = requests.post("https://expfypay.com/api/v1/payments", json=payload, headers=headers)
    if r.status_code == 200:
        data = r.json()
        return data.get("pix_qr_code_url"), data.get("pix_code")
    return None, None


async def start(update: Update, context):
    await update.message.reply_text(
        f"👋 Olá {update.effective_user.first_name}!\nDigite /comprar para gerar seu Pix e entrar no grupo VIP."
    )


async def comprar(update: Update, context):
    user_id = update.effective_user.id
    chat_id = update.message.chat_id
    if user_id in usuarios and usuarios[user_id]["confirmado"]:
        await update.message.reply_text("✅ Você já foi confirmado e tem acesso ao grupo.")
        return
    qr, pix_code = gerar_pix(user_id, VALOR)
    if qr and pix_code:
        usuarios[user_id] = {
            "username": update.effective_user.username,
            "confirmado": False,
            "pix_link": pix_code,
            "chat_id": chat_id
        }
        await update.message.reply_photo(
            photo=qr,
            caption=f"💰 Pague {VALOR:.2f} via Pix\nCopia e cola: <code>{pix_code}</code>\nAguarde a confirmação automática...",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ Não foi possível gerar o Pix.")


async def expfy_webhook(request):
    if request.headers.get("X-Secret-Key", "") != WEBHOOK_KEY:
        return web.Response(status=403, text="Invalid secret")
    data = await request.json()
    external_id = data.get("external_id")
    status = data.get("status")
    if external_id and external_id.isdigit() and status in ["approved", "paid"]:
        user_id = int(external_id)
        if user_id in usuarios and not usuarios[user_id]["confirmado"]:
            usuarios[user_id]["confirmado"] = True
            await tg_app.bot.send_message(
                chat_id=usuarios[user_id]["chat_id"],
                text=f"✅ Pagamento confirmado!\nAcesso: {LINK_GRUPO}"
            )
    return web.Response(text="OK")


async def telegram_webhook(request):
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.update_queue.put(update)
    return web.Response(text="OK")


tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("comprar", comprar))


async def main():
    app = web.Application()
    app.router.add_post("/expfy_webhook", expfy_webhook)
    app.router.add_post(f"/{TOKEN}", telegram_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    await tg_app.initialize()
    await tg_app.start()
    print(f"Bot rodando em porta {PORT}")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())

