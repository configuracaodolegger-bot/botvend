import TelegramBot from "node-telegram-bot-api";
import express from "express";
import fetch from "node-fetch";

const app = express();
app.use(express.json());

const bot = new TelegramBot(process.env.BOT_TOKEN);
const groupLink = process.env.GROUP_LINK;
const expfyPublicKey = process.env.EXPFY_PUBLIC_KEY;
const expfySecretKey = process.env.EXPFY_SECRET_KEY;

const PORT = process.env.PORT || 10000;
const DOMAIN = process.env.RENDER_EXTERNAL_URL || `http://localhost:${PORT}`;
const CALLBACK_URL = `${DOMAIN}/render-webhook`;

const userTransactions = {};

async function createPayment(userId, customerName, customerDocument) {
  const external_id = `user_${userId}_${Date.now()}`;
  const response = await fetch("https://expfypay.com/api/v1/payments", {
    method: "POST",
    headers: {
      "X-Public-Key": expfyPublicKey,
      "X-Secret-Key": expfySecretKey,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      amount: 29.90,
      description: "Acesso ao Grupo VIP",
      customer: { name: customerName, document: customerDocument },
      external_id,
      callback_url: CALLBACK_URL
    })
  });
  const data = await response.json();
  userTransactions[external_id] = userId;
  return { pixCode: data.pix_code, qrUrl: data.pix_qr_code_url, external_id };
}

bot.onText(/\/start/, (msg) => {
  bot.sendMessage(msg.chat.id, "👋 Bem-vindo! Digite /comprar para gerar PIX e acessar o grupo VIP.");
});

bot.onText(/\/comprar/, async (msg) => {
  try {
    const customerName = msg.from.first_name || "Cliente";
    const customerDocument = "000.000.000-00";
    const { pixCode, qrUrl } = await createPayment(msg.from.id, customerName, customerDocument);
    if (qrUrl) await bot.sendPhoto(msg.chat.id, qrUrl, { caption: "📸 Escaneie o QR Code para pagar" });
    await bot.sendMessage(msg.chat.id, `📋 PIX copia e cola:\n<code>${pixCode}</code>`, { parse_mode: "HTML" });
    bot.sendMessage(msg.chat.id, "💡 Assim que o pagamento for confirmado, você receberá acesso automático ao grupo.");
  } catch (err) {
    console.error(err);
    bot.sendMessage(msg.chat.id, "❌ Erro ao gerar PIX. Tente novamente mais tarde.");
  }
});

app.post("/render-webhook", (req, res) => {
  const { external_id, status } = req.body;
  if (!external_id || !userTransactions[external_id]) return res.status(400).send("Invalid external_id");
  const chatId = userTransactions[external_id];
  if (status === "approved" || status === "paid") {
    bot.sendMessage(chatId, `✅ Pagamento confirmado!\nAqui está seu link do grupo VIP: ${groupLink}`);
  }
  res.status(200).send("OK");
});

app.get("/", (req, res) => res.send("Bot rodando 🚀"));
app.listen(PORT, () => console.log(`Bot rodando em ${DOMAIN}`));
