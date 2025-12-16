# Epic Games Store – Free Games Notifier
# ---------------------------------
# Checks Epic Games Store free games once per day
# Sends a modern Discord webhook notification and/or email
# Only notifies if the free game(s) changed

import requests
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ================== CONFIG ==================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1450292543324426415/qRVTC-wxhF4txq7KkwRX3ilUpRFsb25znrU5PXbSlfeoTSNSi9G_SpgdOLafzD1ZBOTU"  # set to None to disable

EMAIL_ENABLED = False
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "your_email@gmail.com"
SMTP_PASSWORD = "your_app_password"
EMAIL_TO = "recipient_email@gmail.com"

STATE_FILE = "last_free_games.json"
# ============================================

EPIC_API_URL = (
    "https://store-site-backend-static.ak.epicgames.com/"
    "freeGamesPromotions?locale=en-US&country=US&allowCountries=US"
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
                if promo.get("discountSetting", {}).get("discountPercentage") == 0:
                    games.append({
                        "title": game["title"],
                        "description": game.get("description", ""),
                        "image": game.get("keyImages", [{}])[0].get("url"),
                        "url": f"https://store.epicgames.com/p/{game['productSlug']}"
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


def send_discord_notification(games):
    if not DISCORD_WEBHOOK_URL:
        return

    embeds = []
    for game in games:
        embeds.append({
            "title": game["title"],
            "url": game["url"],
            "description": game["description"][:300],
            "image": {"url": game["image"]},
            "footer": {"text": "Epic Games Store – Free Game"}
        })

    payload = {
        "username": "Epic Free Games",
        "avatar_url": "https://cdn2.unrealengine.com/egs-logo-400x400-400x400-9aef7e1eaa9f.png",
        "content": "🎮 **New Free Game(s) Available on Epic Games Store!**",
        "embeds": embeds
    }

    requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)


def send_email_notification(games):
    if not EMAIL_ENABLED:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Epic Games – New Free Game Available"
    msg["From"] = SMTP_EMAIL
    msg["To"] = EMAIL_TO

    game_blocks = "".join([
        f"""
        <div style='margin-bottom:20px;'>
            <h2>{g['title']}</h2>
            <p>{g['description']}</p>
            <a href='{g['url']}'>View on Epic Games Store</a>
        </div>
        """ for g in games
    ])

    html = f"""
    <html>
        <body style='font-family:Arial;'>
            <h1>🎮 New Free Game(s) on Epic Games Store</h1>
            {game_blocks}
            <hr>
            <small>Checked on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</small>
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
