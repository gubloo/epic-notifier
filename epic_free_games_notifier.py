# Epic Games Store – Free Games Notifier (GitHub Actions Optimized)
# -------------------------------------------------------------
# - Uses GitHub Actions cache (no git commits)
# - Shows expiry countdown for free games
# - Uses Canadian Epic Games Store (en-CA, country=CA)

import requests
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ================== CONFIG ==================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

EMAIL_ENABLED = bool(os.getenv("EMAIL_ENABLED", False))
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

STATE_FILE = "last_free_games.json"
# ============================================

EPIC_API_URL = (
    "https://store-site-backend-static.ak.epicgames.com/"
    "freeGamesPromotions?locale=en-CA&country=CA&allowCountries=CA"
)


def get_free_games():
    response = requests.get(EPIC_API_URL, timeout=15)
    response.raise_for_status()
    data = response.json()

    games = []
    elements = data["data"]["Catalog"]["searchStore"]["elements"]

    for game in elements:
        promotions = game.get("promotions")
        if not promotions:
            continue

        offers = promotions.get("promotionalOffers", [])
        if not offers:
            continue

        for offer in offers:
            for promo in offer.get("promotionalOffers", []):
                discount = promo.get("discountSetting", {})
                if discount.get("discountPercentage") == 0:
                    end_date = promo.get("endDate")
                    expiry = None
                    if end_date:
                        expiry = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

                    games.append({
                        "title": game["title"],
                        "description": game.get("description", ""),
                        "image": game.get("keyImages", [{}])[0].get("url"),
                        "url": f"https://store.epicgames.com/en-CA/p/{game['productSlug']}",
                        "expiry": expiry.isoformat() if expiry else None
                    })

    return games


def load_last_state():
    if not os.path.exists(STATE_FILE):
        return []
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(games):
    with open(STATE_FILE, "w") as f:
        json.dump(games, f, indent=2)


def format_expiry(expiry_iso):
    if not expiry_iso:
        return "Unknown"

    expiry = datetime.fromisoformat(expiry_iso)
    now = datetime.now(timezone.utc)
    delta = expiry - now

    if delta.days < 0:
        return "Expired"

    days = delta.days
    hours = delta.seconds // 3600
    return f"{days}d {hours}h remaining"


def send_discord_notification(games):
    if not DISCORD_WEBHOOK_URL:
        return

    embeds = []  # <-- THIS is what was missing

    for game in games:
        embeds.append({
            "title": game["title"],
            "url": game["url"],
            "description": (
                f"{game['description'][:250]}\n\n"
                f"⏳ **{format_expiry(game['expiry'])}**"
            ),
            "image": {"url": game["image"]},
            "footer": {"text": "Epic Games Store (Canada)"}
        })

    payload = {
        "username": "Epic Free Games",
        "avatar_url": "https://cdn2.unrealengine.com/egs-logo-400x400-400x400-9aef7e1eaa9f.png",
        "content": "🎮 **New Free Epic Games Available (Canada)**",
        "embeds": embeds
    }

    print("Webhook URL loaded:", bool(DISCORD_WEBHOOK_URL))
    requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

def send_email_notification(games):
    if not EMAIL_ENABLED:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Epic Games – New Free Game (Canada)"
    msg["From"] = SMTP_EMAIL
    msg["To"] = EMAIL_TO

    game_blocks = "".join([
        f"""
        <div style='margin-bottom:24px;'>
            <h2>{g['title']}</h2>
            <p>{g['description']}</p>
            <p><strong>⏳ {format_expiry(g['expiry'])}</strong></p>
            <a href='{g['url']}'>View on Epic Games Store</a>
        </div>
        """ for g in games
    ])

    html = f"""
    <html>
        <body style='font-family:Arial,Helvetica;'>
            <h1>🎮 New Free Epic Games (Canada)</h1>
            {game_blocks}
            <hr>
            <small>Checked {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</small>
        </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)


def main():
    current_games = get_free_games()
    last_games = load_last_state()

    if current_games != last_games and current_games:
        send_discord_notification(current_games)
        send_email_notification(current_games)
        save_state(current_games)
        print("New free game detected. Notification sent.")
    else:
        print("No change in free games.")


if __name__ == "__main__":
    main()
