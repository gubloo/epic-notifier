import os
import json
import requests
from datetime import datetime, timezone

STATE_FILE = "last_games.json"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

EPIC_API_URL = (
    "https://store-site-backend-static.ak.epicgames.com/"
    "freeGamesPromotions?locale=en-CA&country=CA&allowCountries=CA"
)

def load_last_state():
    if not os.path.exists(STATE_FILE):
        return []
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_last_state(games):
    if not games:
        print("⚠️ Not saving empty game list")
        return
    with open(STATE_FILE, "w") as f:
        json.dump(games, f, indent=2)

def fetch_free_games():
    r = requests.get(EPIC_API_URL, timeout=15)
    r.raise_for_status()
    data = r.json()

    games = []

    elements = data["data"]["Catalog"]["searchStore"]["elements"]

    for game in elements:
        promos = game.get("promotions")
        if not promos:
            continue

        # --- CURRENT FREE GAMES ---
        for promo_group in promos.get("promotionalOffers", []):
            for offer in promo_group.get("promotionalOffers", []):
                discount = offer.get("discountSetting", {}).get("discountPercentage")

                if discount == 0:  # 0% price = FREE
                    expiry = offer.get("endDate")

                    games.append({
                        "id": game["id"],
                        "title": game["title"],
                        "description": game.get("description", "No description available"),
                        "url": f"https://store.epicgames.com/en-CA/p/{game['productSlug']}",
                        "image": game["keyImages"][0]["url"],
                        "expiry": expiry,
                    })

        # --- FALLBACK: SOME FREE GAMES SHOW HERE ---
        for promo_group in promos.get("upcomingPromotionalOffers", []):
            for offer in promo_group.get("promotionalOffers", []):
                discount = offer.get("discountSetting", {}).get("discountPercentage")

                if discount == 0:
                    expiry = offer.get("endDate")

                    games.append({
                        "id": game["id"],
                        "title": game["title"],
                        "description": game.get("description", "No description available"),
                        "url": f"https://store.epicgames.com/en-CA/p/{game['productSlug']}",
                        "image": game["keyImages"][0]["url"],
                        "expiry": expiry,
                    })

    # Remove duplicates
    unique = {g["id"]: g for g in games}
    return list(unique.values())

def format_expiry(iso_time):
    end = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    delta = end - now

    days = delta.days
    hours = delta.seconds // 3600

    if days >= 1:
        return f"Free for {days}d {hours}h"
    return f"Free for {hours}h"

def send_discord_notification(games):
    if not DISCORD_WEBHOOK_URL or not games:
        return

    embeds = []
    for game in games:
        embeds.append({
            "title": game["title"],
            "url": game["url"],
            "description": (
                f"{game['description'][:250]}\n\n"
                f"⏳ **{format_expiry(game['expiry'])}**"
            ),
            "image": {"url": game["image"]},
            "footer": {"text": "Epic Games Store — Canada"},
        })

    game_titles = ", ".join(game["title"] for game in games)

    payload = {
        "username": "Epic Free Games",
        "avatar_url": "https://cdn2.unrealengine.com/egs-logo-400x400-400x400-9aef7e1eaa9f.png",
        "content": (
            "@everyone 🎮 **New FREE Epic Games Available (Canada)**\n\n"
            f"🆓 **{game_titles}**"
        ),
        "embeds": embeds,
    }

    response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    print("Discord status:", response.status_code)
    print("Discord response:", response.text)

def main():
    last_games = load_last_state()
    current_games = fetch_free_games()

    if not current_games:
        print("⚠️ No games fetched, skipping")
        return

    last_ids = {g["id"] for g in last_games}
    current_ids = {g["id"] for g in current_games}

    if current_ids != last_ids:
        print("🎉 New games detected")
        send_discord_notification(current_games)
        save_last_state(current_games)
    else:
        print("No changes detected")

if __name__ == "__main__":
    main()
