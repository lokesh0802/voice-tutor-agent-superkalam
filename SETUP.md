# Setup guide (step by step)

## 0. Python 3.11+ (important on Mac)
macOS ships Python 3.9 → pip can only see very old pipecat versions. Fix:
```bash
brew install python@3.12
rm -rf .venv && python3.12 -m venv .venv && source .venv/bin/activate
python --version        # must say 3.11 or 3.12
pip install -U pip && pip install -r requirements.txt
```

## 1. API keys (≈10 min, free credits)
| Key | Where | Notes |
|---|---|---|
| `SARVAM_API_KEY` | https://dashboard.sarvam.ai → API Keys | Free credits on signup. Used for STT (saaras) + TTS (bulbul:v3) |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys | Add ~$5 credit. Used for the LLM (≈ ₹0.5–1 per 5-min session) and embeddings (indexing all 27 chapters ≈ ₹1) |

Put them in `.env` (copy `.env.example`).

## 2. Browser demo (no phone needed)
```bash
python bot.py            # open http://localhost:7860 → click Connect → allow mic → speak
```
Tip: use headphones so the bot doesn't hear itself (a phone call doesn't have this problem).

## 3. Phone number with Twilio (≈15 min)
1. Install ngrok → `ngrok http 7860` → copy host, e.g. `abcd-1234.ngrok-free.app`
2. Twilio console → buy a number (US number is instant, ~$1.15/mo; Indian numbers need a regulatory bundle/KYC).
   Trial accounts can only receive calls from **verified** numbers → verify your own mobile first.
3. Phone Numbers → your number → *A call comes in* → **Webhook**, `https://<ngrok-host>/`, **HTTP POST** → Save
4. Run:
   ```bash
   python bot.py -t twilio -x abcd-1234.ngrok-free.app
   ```
5. Call the number 🎉 (add `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` to `.env` so the bot can hang up itself)

> Indian number alternative: Exotel or Plivo work with the same code — `python bot.py -t exotel` / `-t plivo`.

## 4. Tuning knobs
| What | Where |
|---|---|
| Voice (priya, neha, kavya, rahul, aditya, shubh…) | `SARVAM_VOICE` in `.env` |
| Speaking speed | `SARVAM_PACE` (0.5–2.0) |
| Bot cuts student off / replies too slowly | `VADParams(stop_secs=0.4)` in `bot.py` (raise to 0.6 for slow speakers) |
| Answer length, tone, language | `tutor/prompts.py` |
| Add more books | drop PDFs into `knowledge_base/pdfs/<subject>/NN_name.pdf` → `python scripts/ingest.py` |

## 5. Troubleshooting
- **Bot hears itself / keeps interrupting** → use headphones in the browser.
- **Hindi words sound odd** → make sure the LLM outputs Devanagari for Hindi (prompt rule); romanized Hindi is read like English.
- **First reply slow** → first run downloads the Silero VAD model; later runs are fast.
- **Twilio call connects then silence** → ngrok host in `-x` must match the one in the Twilio webhook, no `https://` in `-x`.

## 6. Docker (optional)
```bash
python scripts/ingest.py   # build index first (copied into the image)
docker build -t voice-tutor . && docker run -p 7860:7860 --env-file .env voice-tutor
```
