"""
Grant Data Aggregator — fetches, parses and caches funding opportunities
from multiple public sources (RSS feeds, government portals, APIs).
"""

import os
import json
import logging
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional
import requests
from bs4 import BeautifulSoup
import feedparser
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join("data", "grants_cache.json")
CACHE_TTL_MINUTES = int(os.getenv("CACHE_REFRESH_INTERVAL", "60"))

# ── Public funding sources ────────────────────────────────────────────────────
GRANT_SOURCES = [
    {
        "id": "startup_india",
        "name": "Startup India",
        "url": "https://www.startupindia.gov.in/content/sih/en/funding.html",
        "type": "scrape",
        "country": "India",
        "tags": ["startup", "india", "government"],
    },
    {
        "id": "dst_nidhi",
        "name": "DST NIDHI Programme",
        "url": "https://nidhi.dst.gov.in/",
        "type": "scrape",
        "country": "India",
        "tags": ["deep-tech", "R&D", "india"],
    },
    {
        "id": "meity_startup",
        "name": "MeitY Startup Hub",
        "url": "https://www.msh.gov.in/",
        "type": "scrape",
        "country": "India",
        "tags": ["tech", "digital", "india"],
    },
    {
        "id": "aicte_schemes",
        "name": "AICTE Research & Innovation Schemes",
        "url": "https://www.aicte-india.org/schemes",
        "type": "scrape",
        "country": "India",
        "tags": ["education", "innovation", "india"],
    },
    {
        "id": "grants_gov",
        "name": "Grants.gov (US Federal)",
        "url": "https://www.grants.gov/rss/GG_NewOppsByAgency.xml",
        "type": "rss",
        "country": "USA",
        "tags": ["federal", "usa", "technology"],
    },
    {
        "id": "ec_horizon",
        "name": "EU Horizon Europe",
        "url": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search",
        "type": "scrape",
        "country": "EU",
        "tags": ["innovation", "eu", "research"],
    },
]

# ── Curated static dataset (always available, no network needed) ──────────────
STATIC_GRANTS = [
    {
        "id": "sid_seed_001",
        "title": "Startup India Seed Fund Scheme (SISFS)",
        "source": "Startup India",
        "source_url": "https://seedfund.startupindia.gov.in/",
        "description": (
            "Provides financial assistance to startups for proof of concept, prototype development, "
            "product trials, market entry, and commercialisation. Grants up to ₹20 lakhs for PoC "
            "and up to ₹50 lakhs as loans for commercialisation."
        ),
        "funding_amount": "₹20 – ₹50 Lakhs",
        "eligibility": (
            "DPIIT-recognised startup, incorporated ≤ 2 years at time of application, "
            "not received > ₹10L from government schemes, has a business idea with social impact."
        ),
        "deadline": "Rolling applications through incubators",
        "domain": ["all sectors"],
        "stage": ["ideation", "validation", "early-stage"],
        "location": "India",
        "tags": ["startup", "seed", "india", "government", "dpiit"],
        "type": "Grant + Loan",
        "last_updated": "2024-01-01",
    },
    {
        "id": "dst_nidhi_prayas",
        "title": "DST NIDHI PRAYAS Programme",
        "source": "DST India",
        "source_url": "https://nidhi.dst.gov.in/prayas.php",
        "description": (
            "Supports early-stage innovators to develop a working prototype from a concept/idea. "
            "Grants up to ₹10 lakhs to individual innovators and startups for building prototypes."
        ),
        "funding_amount": "Up to ₹10 Lakhs",
        "eligibility": (
            "Indian citizen, proof of concept or idea at any stage of technology development, "
            "working with an empanelled Prayas Centre."
        ),
        "deadline": "Rolling",
        "domain": ["deep-tech", "hardware", "science", "engineering"],
        "stage": ["ideation", "prototype"],
        "location": "India",
        "tags": ["dst", "deep-tech", "prototype", "india"],
        "type": "Grant",
        "last_updated": "2024-01-01",
    },
    {
        "id": "meity_tide_20",
        "title": "MeitY TIDE 2.0 Programme",
        "source": "MeitY",
        "source_url": "https://tide20.meity.gov.in/",
        "description": (
            "Technology Incubation and Development of Entrepreneurs programme supporting "
            "ICT-based tech startups. Provides equity-free funding, mentorship, and market access."
        ),
        "funding_amount": "Up to ₹75 Lakhs",
        "eligibility": (
            "ICT-based startups, DPIIT recognised preferred, incubated at MeitY-empanelled incubator, "
            "product must be in ICT domain."
        ),
        "deadline": "Rolling through empanelled incubators",
        "domain": ["ICT", "fintech", "healthtech", "edtech", "AI"],
        "stage": ["early-stage", "growth"],
        "location": "India",
        "tags": ["meity", "ict", "fintech", "india", "equity-free"],
        "type": "Grant",
        "last_updated": "2024-01-01",
    },
    {
        "id": "aicte_innovation_001",
        "title": "AICTE Idea Lab & Innovation Grant",
        "source": "AICTE",
        "source_url": "https://www.aicte-india.org/schemes/students-development-schemes/IDEA-Lab",
        "description": (
            "Supports student-led startups and innovations emerging from technical institutions. "
            "Grants up to ₹35 lakhs for setting up idea labs and funding prototypes."
        ),
        "funding_amount": "Up to ₹35 Lakhs",
        "eligibility": (
            "Students/faculty of AICTE-approved institutions, project must relate to social/technical "
            "challenges, team of 2–5 members."
        ),
        "deadline": "Annual cycle — typically June–August",
        "domain": ["education", "technology", "social impact", "engineering"],
        "stage": ["ideation", "prototype"],
        "location": "India",
        "tags": ["aicte", "student", "innovation", "india"],
        "type": "Grant",
        "last_updated": "2024-01-01",
    },
    {
        "id": "birac_biotechnology",
        "title": "BIRAC BIG (Biotechnology Ignition Grant)",
        "source": "BIRAC",
        "source_url": "https://birac.nic.in/big.php",
        "description": (
            "Supports innovative and high-risk early-stage research at the proof-of-concept stage "
            "in the area of biotechnology. Provides up to ₹50 lakhs as an ignition grant."
        ),
        "funding_amount": "Up to ₹50 Lakhs",
        "eligibility": (
            "Individual innovators, startups, early-stage companies; Indian national or Indian-registered entity; "
            "research must be in biotech/life sciences."
        ),
        "deadline": "Rolling, bi-annual calls",
        "domain": ["biotechnology", "life sciences", "health", "agri-biotech"],
        "stage": ["ideation", "early-stage", "prototype"],
        "location": "India",
        "tags": ["birac", "biotech", "health", "india"],
        "type": "Grant",
        "last_updated": "2024-01-01",
    },
    {
        "id": "atal_innovation_atal_grants",
        "title": "AIM – Atal New India Challenge (ANIC)",
        "source": "NITI Aayog / AIM",
        "source_url": "https://aim.gov.in/anic.php",
        "description": (
            "Seeks to find, fund, and support technology-based innovations to solve sector-specific "
            "challenges of national importance. Provides up to ₹1 crore in grant funding."
        ),
        "funding_amount": "Up to ₹1 Crore",
        "eligibility": (
            "Indian startups, MSMEs, individual innovators; solution must address the announced "
            "problem statement; must have a working prototype or proof of concept."
        ),
        "deadline": "Challenge-specific open calls",
        "domain": ["all sectors", "social impact", "deep-tech"],
        "stage": ["prototype", "early-stage", "growth"],
        "location": "India",
        "tags": ["aim", "anic", "niti aayog", "challenge", "india"],
        "type": "Challenge Grant",
        "last_updated": "2024-01-01",
    },
    {
        "id": "nsf_sbir",
        "title": "NSF SBIR / STTR Phase I",
        "source": "National Science Foundation (USA)",
        "source_url": "https://seedfund.nsf.gov/",
        "description": (
            "America's Seed Fund powered by NSF — provides non-dilutive funding to deep-tech startups "
            "for R&D. Phase I awards up to $275,000 for 6–12 month feasibility studies."
        ),
        "funding_amount": "Up to $275,000 (Phase I)",
        "eligibility": (
            "US-based small business (< 500 employees), US citizen or permanent resident PI, "
            "research must have potential for commercialisation and societal benefit."
        ),
        "deadline": "Three annual solicitation windows",
        "domain": ["deep-tech", "science", "engineering", "AI", "biotech"],
        "stage": ["early-stage", "prototype"],
        "location": "USA",
        "tags": ["nsf", "sbir", "sttr", "usa", "non-dilutive"],
        "type": "Grant",
        "last_updated": "2024-01-01",
    },
    {
        "id": "eu_eic_accelerator",
        "title": "EIC Accelerator (EU Horizon Europe)",
        "source": "European Innovation Council",
        "source_url": "https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en",
        "description": (
            "Supports high-risk, high-potential individual SMEs and startups to develop and scale up "
            "breakthrough innovations. Provides up to €2.5M grant + €15M equity investment."
        ),
        "funding_amount": "Up to €2.5M grant + €15M equity",
        "eligibility": (
            "EU/associated country SME or startup, breakthrough innovation with high TRL, "
            "strong market potential, scalable business model."
        ),
        "deadline": "Three cut-off dates per year",
        "domain": ["deep-tech", "climate", "health", "digital", "space"],
        "stage": ["growth", "scale-up"],
        "location": "EU / Europe",
        "tags": ["eic", "eu", "horizon", "equity", "deep-tech"],
        "type": "Grant + Equity",
        "last_updated": "2024-01-01",
    },
    {
        "id": "wbf_women_startup",
        "title": "Women Entrepreneurship Platform (WEP) – NITI Aayog",
        "source": "NITI Aayog WEP",
        "source_url": "https://wep.gov.in/",
        "description": (
            "Supports women-led startups with funding, mentorship, and market access. "
            "Connects women entrepreneurs with investors, incubators, and grant programmes."
        ),
        "funding_amount": "Varies by scheme",
        "eligibility": (
            "Women-led startup (51%+ ownership), DPIIT recognised preferred, "
            "any sector and stage."
        ),
        "deadline": "Rolling",
        "domain": ["all sectors"],
        "stage": ["all stages"],
        "location": "India",
        "tags": ["women", "wep", "niti aayog", "india", "diversity"],
        "type": "Grant + Support",
        "last_updated": "2024-01-01",
    },
    {
        "id": "nasscom_futureskills",
        "title": "NASSCOM Deep Tech Club Funding Access",
        "source": "NASSCOM",
        "source_url": "https://nasscom.in/deep-tech",
        "description": (
            "Connects deep-tech startups with curated funding opportunities, corporate partnerships, "
            "and government grant programmes. Focus on AI, blockchain, IoT, and quantum computing."
        ),
        "funding_amount": "Varies",
        "eligibility": (
            "Deep-tech startup in AI, ML, blockchain, IoT, or quantum computing; "
            "any stage; preference for Indian-registered entities."
        ),
        "deadline": "Rolling",
        "domain": ["AI", "blockchain", "IoT", "quantum", "deep-tech"],
        "stage": ["all stages"],
        "location": "India",
        "tags": ["nasscom", "deep-tech", "AI", "india"],
        "type": "Programme Access",
        "last_updated": "2024-01-01",
    },
]


class GrantAggregator:
    """Aggregates grants from static dataset + live web scraping with caching."""

    def __init__(self):
        self._cache: dict = {}
        self._cache_time: Optional[datetime] = None
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all_grants(self, force_refresh: bool = False) -> list[dict]:
        """Return combined grants (static + cached live data)."""
        if force_refresh or self._is_cache_stale():
            self._refresh_live_grants()
        live = list(self._cache.get("grants", {}).values())
        combined = {g["id"]: g for g in STATIC_GRANTS}
        combined.update({g["id"]: g for g in live})
        return list(combined.values())

    def get_grant_by_id(self, grant_id: str) -> Optional[dict]:
        all_grants = {g["id"]: g for g in self.get_all_grants()}
        return all_grants.get(grant_id)

    def search_grants(
        self,
        query: str = "",
        domains: list[str] = None,
        stages: list[str] = None,
        location: str = "",
        funding_type: str = "",
    ) -> list[dict]:
        """Filter grants by keyword, domain, stage, location."""
        grants = self.get_all_grants()
        results = []
        query_lower = query.lower()
        for g in grants:
            if query_lower and not self._text_matches(g, query_lower):
                continue
            if domains and not self._domain_matches(g, domains):
                continue
            if stages and not self._stage_matches(g, stages):
                continue
            if location and location.lower() not in g.get("location", "").lower():
                if location.lower() not in [t.lower() for t in g.get("tags", [])]:
                    continue
            if funding_type and funding_type.lower() not in g.get("type", "").lower():
                continue
            results.append(g)
        return results

    # ------------------------------------------------------------------
    # Live scraping
    # ------------------------------------------------------------------

    def _refresh_live_grants(self):
        """Attempt to scrape live grants from all sources."""
        logger.info("Refreshing live grant data from %d sources…", len(GRANT_SOURCES))
        for source in GRANT_SOURCES:
            try:
                if source["type"] == "rss":
                    grants = self._fetch_rss(source)
                else:
                    grants = self._fetch_scrape(source)
                for g in grants:
                    self._cache.setdefault("grants", {})[g["id"]] = g
                logger.info("  ✓ %s — %d grants", source["name"], len(grants))
            except Exception as exc:
                logger.warning("  ✗ %s — %s", source["name"], exc)

        self._cache_time = datetime.utcnow()
        self._save_cache()

    def _fetch_rss(self, source: dict) -> list[dict]:
        feed = feedparser.parse(source["url"])
        grants = []
        for entry in feed.entries[:15]:
            gid = hashlib.md5(entry.get("link", entry.title).encode()).hexdigest()[:12]
            grants.append({
                "id": f"{source['id']}_{gid}",
                "title": entry.get("title", "No title"),
                "source": source["name"],
                "source_url": entry.get("link", source["url"]),
                "description": BeautifulSoup(
                    entry.get("summary", ""), "lxml"
                ).get_text()[:500],
                "funding_amount": "See listing",
                "eligibility": "See grant listing for details",
                "deadline": entry.get("published", "See listing"),
                "domain": source.get("tags", []),
                "stage": ["all stages"],
                "location": source.get("country", ""),
                "tags": source.get("tags", []),
                "type": "Federal Grant",
                "last_updated": datetime.utcnow().isoformat(),
            })
        return grants

    def _fetch_scrape(self, source: dict) -> list[dict]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; GrantFinderBot/1.0)"}
        resp = requests.get(source["url"], headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        grants = []
        # Generic heuristic: find headings that look like grant titles
        for tag in soup.find_all(["h2", "h3", "h4"])[:10]:
            text = tag.get_text(strip=True)
            if len(text) < 10 or len(text) > 200:
                continue
            desc_tag = tag.find_next_sibling(["p", "div"])
            desc = desc_tag.get_text(strip=True)[:400] if desc_tag else ""
            gid = hashlib.md5(text.encode()).hexdigest()[:12]
            grants.append({
                "id": f"{source['id']}_{gid}",
                "title": text,
                "source": source["name"],
                "source_url": source["url"],
                "description": desc or f"Visit {source['url']} for full details.",
                "funding_amount": "See listing",
                "eligibility": "See grant listing for details",
                "deadline": "See listing",
                "domain": source.get("tags", []),
                "stage": ["all stages"],
                "location": source.get("country", ""),
                "tags": source.get("tags", []),
                "type": "Grant",
                "last_updated": datetime.utcnow().isoformat(),
            })
        return grants

    # ------------------------------------------------------------------
    # Matching helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _text_matches(grant: dict, query: str) -> bool:
        searchable = " ".join([
            grant.get("title", ""),
            grant.get("description", ""),
            grant.get("eligibility", ""),
            " ".join(grant.get("tags", [])),
            " ".join(grant.get("domain", [])),
        ]).lower()
        return query in searchable

    @staticmethod
    def _domain_matches(grant: dict, domains: list[str]) -> bool:
        grant_domains = [d.lower() for d in grant.get("domain", [])]
        grant_tags = [t.lower() for t in grant.get("tags", [])]
        for d in domains:
            dl = d.lower()
            if dl in grant_domains or dl in grant_tags or "all sectors" in grant_domains:
                return True
        return False

    @staticmethod
    def _stage_matches(grant: dict, stages: list[str]) -> bool:
        grant_stages = [s.lower() for s in grant.get("stage", [])]
        for s in stages:
            sl = s.lower()
            if sl in grant_stages or "all stages" in grant_stages:
                return True
        return False

    # ------------------------------------------------------------------
    # Cache persistence
    # ------------------------------------------------------------------

    def _is_cache_stale(self) -> bool:
        if not self._cache_time:
            return True
        return datetime.utcnow() - self._cache_time > timedelta(minutes=CACHE_TTL_MINUTES)

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cache = data.get("grants_data", {})
                    ts = data.get("timestamp")
                    self._cache_time = datetime.fromisoformat(ts) if ts else None
                logger.info("Cache loaded from %s", CACHE_FILE)
            except Exception as exc:
                logger.warning("Could not load cache: %s", exc)

    def _save_cache(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "grants_data": self._cache,
                        "timestamp": self._cache_time.isoformat() if self._cache_time else None,
                    },
                    f,
                    indent=2,
                )
        except Exception as exc:
            logger.warning("Could not save cache: %s", exc)
