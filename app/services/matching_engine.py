"""
Personalisation & Matching Engine — scores grants against a startup profile
using TF-IDF similarity + IBM Granite AI re-ranking.
"""

import logging
import math
import re
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

# ── Startup domain taxonomy ───────────────────────────────────────────────────
DOMAIN_KEYWORDS = {
    "AI": ["artificial intelligence", "machine learning", "deep learning", "nlp", "computer vision", "ai", "ml"],
    "fintech": ["fintech", "payments", "banking", "insurance", "lending", "blockchain", "crypto", "defi", "neobank"],
    "healthtech": ["health", "medical", "healthcare", "medtech", "biotech", "clinical", "hospital", "patient"],
    "edtech": ["education", "learning", "e-learning", "school", "university", "training", "skill", "edtech"],
    "agritech": ["agriculture", "farming", "agri", "crop", "irrigation", "farmer", "agritech", "food"],
    "cleantech": ["climate", "clean energy", "solar", "renewable", "sustainability", "carbon", "greentech", "ev"],
    "deep-tech": ["deep tech", "quantum", "semiconductor", "robotics", "drone", "aerospace", "nanotechnology"],
    "ICT": ["software", "saas", "platform", "mobile app", "cloud", "cybersecurity", "iot", "api"],
    "social-impact": ["social", "ngo", "inclusion", "rural", "poverty", "disability", "women", "tribal"],
    "logistics": ["logistics", "supply chain", "transportation", "last-mile", "warehouse", "fleet"],
    "manufacturing": ["manufacturing", "industry 4.0", "3d printing", "smart factory", "automation"],
    "biotech": ["biotechnology", "genomics", "bioinformatics", "pharmaceutical", "drug discovery"],
}

STAGE_ORDER = ["ideation", "validation", "prototype", "early-stage", "growth", "scale-up"]


class MatchingEngine:
    """
    Scores each grant against a startup profile using:
    1. TF-IDF / keyword cosine similarity (fast, offline)
    2. Optional IBM Granite re-ranking (adds AI relevance score)
    """

    def __init__(self, granite_service=None):
        self._granite = granite_service

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def rank_grants(
        self,
        startup_profile: dict,
        grants: list[dict],
        use_ai: bool = True,
        top_n: int = 20,
    ) -> list[dict]:
        """
        Return top-N grants ranked for this startup profile.
        Each grant gets: relevance_score (0–100), match_tags, match_reason.
        """
        if not grants:
            return []

        # Step 1: keyword/TF-IDF scoring
        profile_text = self._profile_to_query(startup_profile)
        corpus = [self._grant_to_text(g) for g in grants]
        tfidf_scores = self._tfidf_similarity(profile_text, corpus)

        scored = []
        for grant, sim in zip(grants, tfidf_scores):
            bonus = self._rule_bonus(startup_profile, grant)
            base_score = min(100, int(sim * 100 + bonus))
            match_tags = self._extract_match_tags(startup_profile, grant)
            scored.append({
                **grant,
                "relevance_score": base_score,
                "match_tags": match_tags,
                "match_reason": f"Keyword match score: {base_score}/100",
            })

        scored.sort(key=lambda g: g["relevance_score"], reverse=True)
        top = scored[:top_n]

        # Step 2: AI re-ranking with Granite (optional)
        if use_ai and self._granite:
            try:
                top = self._ai_rerank(startup_profile, top)
            except Exception as exc:
                logger.warning("Granite re-ranking failed, using keyword scores: %s", exc)

        return top

    # ------------------------------------------------------------------
    # TF-IDF similarity
    # ------------------------------------------------------------------

    def _tfidf_similarity(self, query: str, corpus: list[str]) -> list[float]:
        """Compute cosine similarity between query and each document."""
        all_docs = [query] + corpus
        tokenized = [self._tokenize(d) for d in all_docs]

        # build vocabulary
        vocab = set()
        for tokens in tokenized:
            vocab.update(tokens)
        vocab = sorted(vocab)
        vocab_idx = {w: i for i, w in enumerate(vocab)}

        n = len(all_docs)
        tf_idf_matrix = []
        df = Counter()
        for tokens in tokenized:
            freq = Counter(tokens)
            df.update(freq.keys())
            tf_idf_matrix.append(freq)

        idf = {w: math.log(n / (1 + df[w])) for w in vocab}

        def vec(freq_dict):
            v = [0.0] * len(vocab)
            total = sum(freq_dict.values()) or 1
            for w, c in freq_dict.items():
                if w in vocab_idx:
                    v[vocab_idx[w]] = (c / total) * idf[w]
            return v

        query_vec = vec(tf_idf_matrix[0])
        scores = []
        for doc_freq in tf_idf_matrix[1:]:
            doc_vec = vec(doc_freq)
            scores.append(self._cosine(query_vec, doc_vec))
        return scores

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    # ------------------------------------------------------------------
    # Rule-based bonus scoring
    # ------------------------------------------------------------------

    def _rule_bonus(self, profile: dict, grant: dict) -> int:
        bonus = 0
        # Location match
        ploc = profile.get("location", "").lower()
        gloc = grant.get("location", "").lower()
        if ploc and gloc and (ploc in gloc or gloc in ploc):
            bonus += 20
        elif gloc in ("india", "all", "global"):
            bonus += 10

        # Stage match
        pstage = profile.get("stage", "").lower()
        gstages = [s.lower() for s in grant.get("stage", [])]
        if pstage in gstages or "all stages" in gstages:
            bonus += 15

        # Domain match
        pdomains = self._infer_domains(profile)
        gdomains = [d.lower() for d in grant.get("domain", [])] + [t.lower() for t in grant.get("tags", [])]
        if "all sectors" in gdomains:
            bonus += 5
        for d in pdomains:
            if d.lower() in gdomains:
                bonus += 10
                break
        return bonus

    # ------------------------------------------------------------------
    # AI re-ranking
    # ------------------------------------------------------------------

    def _ai_rerank(self, startup_profile: dict, grants: list[dict]) -> list[dict]:
        """Call IBM Granite to rescore top grants — merges AI + keyword scores."""
        ai_scored = self._granite.match_grants_to_startup(startup_profile, grants)
        id_to_ai = {g["id"]: g for g in ai_scored}
        result = []
        for g in grants:
            ai = id_to_ai.get(g["id"], {})
            ai_score = ai.get("ai_score", g["relevance_score"])
            kw_score = g["relevance_score"]
            # Weighted blend: 60% AI, 40% keyword
            final = int(0.6 * ai_score + 0.4 * kw_score)
            result.append({
                **g,
                "relevance_score": min(final, 100),
                "ai_score": ai_score,
                "match_reason": ai.get("match_reason", g.get("match_reason", "")),
            })
        result.sort(key=lambda g: g["relevance_score"], reverse=True)
        return result

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        text = text.lower()
        tokens = re.findall(r"[a-z]{2,}", text)
        stopwords = {
            "the", "and", "for", "are", "this", "that", "with", "from",
            "have", "has", "will", "can", "its", "not", "any", "all",
            "our", "your", "their", "they", "been", "more", "also",
        }
        return [t for t in tokens if t not in stopwords]

    @staticmethod
    def _profile_to_query(profile: dict) -> str:
        parts = [
            profile.get("name", ""),
            profile.get("domain", ""),
            profile.get("problem", ""),
            profile.get("solution", ""),
            profile.get("stage", ""),
            profile.get("location", ""),
            profile.get("keywords", ""),
        ]
        return " ".join(p for p in parts if p)

    @staticmethod
    def _grant_to_text(grant: dict) -> str:
        return " ".join([
            grant.get("title", ""),
            grant.get("description", ""),
            grant.get("eligibility", ""),
            " ".join(grant.get("tags", [])),
            " ".join(grant.get("domain", [])),
            grant.get("location", ""),
        ])

    @classmethod
    def _infer_domains(cls, profile: dict) -> list[str]:
        profile_text = cls._profile_to_query(profile).lower()
        matched = []
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(kw in profile_text for kw in keywords):
                matched.append(domain)
        return matched or ["all sectors"]

    @staticmethod
    def _extract_match_tags(profile: dict, grant: dict) -> list[str]:
        tags = []
        ploc = profile.get("location", "").lower()
        gloc = grant.get("location", "").lower()
        if ploc and (ploc in gloc or gloc in ploc):
            tags.append("📍 Location match")
        pstage = profile.get("stage", "").lower()
        gstages = [s.lower() for s in grant.get("stage", [])]
        if pstage in gstages or "all stages" in gstages:
            tags.append("🚀 Stage match")
        gdomains = [d.lower() for d in grant.get("domain", [])]
        if "all sectors" in gdomains:
            tags.append("🌐 Open to all sectors")
        return tags
