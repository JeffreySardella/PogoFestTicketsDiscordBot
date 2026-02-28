import aiohttp
import json
import logging
import os

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Events to monitor
# All three in-person event pages are live at pokemongo.com/en/gofest/{city}.
# Currently they show a countdown + "Check back for more information in March 2026!".
# The Global page URL is TBA — add it here once Niantic publishes it.
# ---------------------------------------------------------------------------
EVENTS = [
    {
        "name": "GO Fest 2026: Tokyo",
        "location": "Tokyo, Japan",
        "dates": "May 29 – June 1, 2026",
        "url": "https://pokemongo.com/en/gofest/tokyo",
    },
    {
        "name": "GO Fest 2026: Chicago",
        "location": "Chicago, IL, USA",
        "dates": "June 5–7, 2026",
        "url": "https://pokemongo.com/en/gofest/chicago",
    },
    {
        "name": "GO Fest 2026: Copenhagen",
        "location": "Copenhagen, Denmark",
        "dates": "June 12–14, 2026",
        "url": "https://pokemongo.com/en/gofest/copenhagen",
    },
    # Global event page URL is not yet live — uncomment and update when published:
    # {
    #     "name": "GO Fest 2026: Global",
    #     "location": "Global (In-Game)",
    #     "dates": "TBA",
    #     "url": "https://pokemongo.com/en/gofest/global",
    # },
]

# Keywords in visible page text that confirm tickets are on sale.
# When the event pages go live for ticketing, they will likely contain one of these.
BUY_KEYWORDS = ["buy now", "get tickets", "purchase tickets", "buy tickets", "order now"]

# Phrases currently on the countdown pages that mean tickets are NOT available yet.
# "check back" covers "Check back for more information in March 2026!" which all
# three event pages currently display.
UNAVAIL_PHRASES = ["check back", "sold out", "not yet available"]

# Niantic's ticketing pipeline: pokemongo.com/en/tickets redirects here.
# When a ticket purchase link appears on an event page, it will point to one of these.
TICKETING_DOMAINS = ("store.pokemongo.com", "tickets.nianticlabs.com")

STATE_FILE = "ticket_state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class TicketMonitor:
    def __init__(self):
        self.state = self._load_state()
        # In-memory status used by /status command
        self.current_status: dict[str, dict] = {
            event["name"]: {"available": False, "status": "Not checked yet"}
            for event in EVENTS
        }

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> dict:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        return {}

    def _save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)

    # ------------------------------------------------------------------
    # Per-event check
    # ------------------------------------------------------------------

    async def _check_event(
        self, session: aiohttp.ClientSession, event: dict
    ) -> tuple[bool, str]:
        """
        Fetch the event page and detect whether tickets are available.

        Returns:
            (is_available, status_text)

        Detection strategy (pokemongo.com/en/gofest/* pages are server-side rendered):
        1. Page must return HTTP 200.
        2. If visible text contains an UNAVAIL_PHRASE (e.g. "check back") → not available.
        3. If an anchor href points to store.pokemongo.com or tickets.nianticlabs.com → available.
           (This is how the "buy tickets" flow works — the page links to the Niantic store.)
        4. Fallback: if visible text contains a BUY_KEYWORD → available.
        """
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with session.get(event["url"], headers=HEADERS, timeout=timeout) as resp:
                if resp.status != 200:
                    logger.warning("HTTP %d for %s", resp.status, event["name"])
                    return False, f"HTTP {resp.status}"

                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                text_lower = soup.get_text(separator=" ").lower()

                # 1. "Check back" / "sold out" phrases mean not yet available
                for phrase in UNAVAIL_PHRASES:
                    if phrase in text_lower:
                        return False, "Not yet available (countdown active)"

                # 2. Niantic ticketing link present on the page
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].lower()
                    if any(domain in href for domain in TICKETING_DOMAINS):
                        return True, f"Available — Tickets On Sale! ({a_tag['href']})"

                # 3. Generic buy keyword in visible text
                for phrase in BUY_KEYWORDS:
                    if phrase in text_lower:
                        return True, "Available — Buy Now!"

                return False, "Not yet available"

        except aiohttp.ClientError as exc:
            logger.error("Network error checking %s: %s", event["name"], exc)
            return False, "Check failed (network error)"
        except Exception as exc:
            logger.error("Unexpected error checking %s: %s", event["name"], exc)
            return False, "Check failed"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_all(self) -> list[dict]:
        """
        Check every event. Returns a list of events that *newly* became
        available since the last check.
        """
        newly_available: list[dict] = []

        async with aiohttp.ClientSession() as session:
            for event in EVENTS:
                is_available, status_text = await self._check_event(session, event)

                name = event["name"]
                was_available: bool = self.state.get(name, {}).get("available", False)

                self.current_status[name] = {
                    "available": is_available,
                    "status": status_text,
                }
                self.state[name] = {
                    "available": is_available,
                    "status": status_text,
                }

                if is_available and not was_available:
                    logger.info("NEW AVAILABILITY: %s", name)
                    newly_available.append(event)

        self._save_state()
        return newly_available

    def get_events_status(self) -> list[dict]:
        """Return current in-memory status for all events (used by /status)."""
        result = []
        for event in EVENTS:
            info = self.current_status.get(
                event["name"], {"available": False, "status": "Not checked yet"}
            )
            result.append(
                {
                    "name": event["name"],
                    "available": info["available"],
                    "status": info["status"],
                    "url": event["url"],
                }
            )
        return result
