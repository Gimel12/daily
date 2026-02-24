"""
Domain Categorization & Alerting
Automatically flags and categorizes domains by type.
Works purely from DNS data — no phone access needed.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("domain_categories")

CATEGORIES = {
    "adult": {
        "label": "Adult Content",
        "severity": "high",
        "domains": [
            "pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com",
            "redtube.com", "youporn.com", "tube8.com", "spankbang.com",
            "brazzers.com", "chaturbate.com", "stripchat.com", "onlyfans.com",
            "bongacams.com", "livejasmin.com", "cam4.com", "myfreecams.com",
            "porntrex.com", "eporner.com", "hqporner.com", "daftsex.com",
            "fapello.com", "rule34.xxx", "nhentai.net", "hanime.tv",
            "hentaihaven.xxx", "literotica.com", "sexstories.com",
            "fuq.com", "bellesa.co", "ixxx.com", "thumbzilla.com",
        ],
        "keywords": ["porn", "xxx", "nsfw", "hentai", "onlyfans", "fap", "nude", "sexo"],
    },
    "dating": {
        "label": "Dating / Hookup",
        "severity": "medium",
        "domains": [
            "tinder.com", "bumble.com", "hinge.co", "grindr.com",
            "okcupid.com", "pof.com", "match.com", "badoo.com",
            "meetme.com", "skout.com", "yubo.live", "omegle.com",
            "chatroulette.com", "monkey.app", "chatrandom.com",
            "ome.tv", "camsurf.com",
        ],
        "keywords": ["hookup", "dating", "chat-random"],
    },
    "vpn_proxy": {
        "label": "VPN / Proxy / Bypass",
        "severity": "medium",
        "domains": [
            "nordvpn.com", "expressvpn.com", "surfshark.com", "protonvpn.com",
            "privateinternetaccess.com", "cyberghostvpn.com", "windscribe.com",
            "hotspotshield.com", "tunnelbear.com", "hide.me", "psiphon.ca",
            "ultrasurf.us", "torproject.org",
            "1dot1dot1dot1.cloudflare-dns.com",
            "dns.google", "dns.cloudflare.com", "doh.opendns.com",
        ],
        "keywords": ["vpn", "unblock", "anonymo", "proxy-"],
    },
    "social_media": {
        "label": "Social Media",
        "severity": "low",
        "domains": [
            "tiktok.com", "instagram.com", "snapchat.com", "facebook.com",
            "twitter.com", "x.com", "reddit.com", "tumblr.com",
            "pinterest.com", "threads.net", "bsky.app", "mastodon.social",
            "discord.com", "discordapp.com", "telegram.org", "t.me",
            "whatsapp.com", "signal.org",
        ],
        "keywords": [],
    },
    "gaming": {
        "label": "Gaming",
        "severity": "low",
        "domains": [
            "roblox.com", "fortnite.com", "epicgames.com", "steampowered.com",
            "minecraft.net", "twitch.tv", "origin.com",
            "ea.com", "xbox.com", "playstation.com", "nintendo.com",
            "riot.games", "blizzard.com", "valve.com", "riotgames.com",
        ],
        "keywords": [],
    },
    "streaming": {
        "label": "Streaming / Video",
        "severity": "low",
        "domains": [
            "youtube.com", "netflix.com", "hulu.com", "disneyplus.com",
            "hbomax.com", "max.com", "peacocktv.com", "paramountplus.com",
            "crunchyroll.com", "funimation.com",
            "spotify.com", "soundcloud.com", "music.apple.com",
        ],
        "keywords": [],
    },
    "gambling": {
        "label": "Gambling",
        "severity": "high",
        "domains": [
            "draftkings.com", "fanduel.com", "betmgm.com", "caesars.com",
            "bet365.com", "bovada.lv", "pokerstars.com", "888poker.com",
            "stake.com", "rollbit.com",
        ],
        "keywords": ["casino", "gambling", "betting", "slots", "sportsbet"],
    },
    "drugs": {
        "label": "Drugs / Substances",
        "severity": "high",
        "domains": [
            "erowid.org", "leafly.com", "weedmaps.com",
        ],
        "keywords": ["weed", "cannabis", "drugs-forum", "vapestore"],
    },
    "weapons": {
        "label": "Weapons",
        "severity": "high",
        "domains": [
            "gunbroker.com", "budsgunshop.com", "palmettostatearmory.com",
        ],
        "keywords": [],
    },
    "self_harm": {
        "label": "Self-Harm / Crisis",
        "severity": "high",
        "domains": [
            "suicidepreventionlifeline.org", "988lifeline.org",
            "crisistextline.org",
        ],
        "keywords": ["self-harm", "suicide"],
    },
}


def categorize_domain(domain: str) -> Optional[Dict]:
    """
    Check if a domain belongs to a known category.
    Returns {"category": "adult", "label": "...", "severity": "high"} or None.
    """
    domain = domain.lower().rstrip(".")

    for cat_id, cat in CATEGORIES.items():
        for known_domain in cat["domains"]:
            if domain == known_domain or domain.endswith("." + known_domain):
                return {
                    "category": cat_id,
                    "label": cat["label"],
                    "severity": cat["severity"],
                }

        for keyword in cat["keywords"]:
            if keyword in domain:
                return {
                    "category": cat_id,
                    "label": cat["label"],
                    "severity": cat["severity"],
                }

    return None


def categorize_batch(domains: List[str]) -> Dict[str, List[Dict]]:
    """
    Categorize a list of domains.
    Returns {category: [{domain, label, severity}, ...]}.
    """
    results = {}
    for domain in set(domains):
        cat = categorize_domain(domain)
        if cat:
            cat_id = cat["category"]
            if cat_id not in results:
                results[cat_id] = []
            results[cat_id].append({
                "domain": domain,
                "label": cat["label"],
                "severity": cat["severity"],
            })
    return results


def get_alerts_from_queries(queries: List[Dict]) -> List[Dict]:
    """
    Scan a list of DNS query records for concerning domains.
    Returns alerts sorted by severity (high first).
    """
    alerts = []
    seen = set()

    for q in queries:
        domain = q.get("domain", "").lower()
        if domain in seen:
            continue

        cat = categorize_domain(domain)
        if cat and cat["severity"] in ("high", "medium"):
            seen.add(domain)
            alerts.append({
                "domain": domain,
                "category": cat["category"],
                "label": cat["label"],
                "severity": cat["severity"],
                "source_ip": q.get("source_ip", ""),
                "timestamp": q.get("timestamp", ""),
            })

    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 3))
    return alerts
