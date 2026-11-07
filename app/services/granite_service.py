"""
IBM Granite AI Service — Core LLM integration via IBM watsonx.ai
Uses IBM Granite 13B Instruct model for all AI-driven features.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GraniteAIService:
    """
    Wraps IBM watsonx.ai SDK to call IBM Granite models.
    Falls back to a rule-based stub when credentials are not yet configured
    so the app remains runnable during local dev without live API keys.
    """

    def __init__(self):
        self.api_key = os.getenv("IBM_API_KEY", "")
        self.url = os.getenv("IBM_WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
        self.project_id = os.getenv("IBM_PROJECT_ID", "")
        self.model_id = os.getenv("IBM_GRANITE_MODEL_ID", "ibm/granite-13b-instruct-v2")
        self._model = None
        self._initialized = False
        self._init_model()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_model(self):
        """Lazily initialise the watsonx.ai ModelInference client."""
        if not self.api_key or self.api_key == "your_ibm_cloud_api_key_here":
            logger.warning(
                "IBM_API_KEY not configured — Granite AI running in STUB mode. "
                "Set real credentials in .env to enable live AI features."
            )
            return

        try:
            from ibm_watsonx_ai import APIClient, Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference
            from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

            creds = Credentials(url=self.url, api_key=self.api_key)
            client = APIClient(creds)

            self._model = ModelInference(
                model_id=self.model_id,
                api_client=client,
                project_id=self.project_id,
                params={
                    GenParams.MAX_NEW_TOKENS: 1024,
                    GenParams.TEMPERATURE: 0.7,
                    GenParams.TOP_P: 0.9,
                    GenParams.REPETITION_PENALTY: 1.1,
                },
            )
            self._initialized = True
            logger.info("IBM Granite model initialised: %s", self.model_id)

        except ImportError:
            logger.error("ibm-watsonx-ai package not installed. Run: pip install ibm-watsonx-ai")
        except Exception as exc:
            logger.error("Failed to initialise IBM Granite model: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """Send a prompt to IBM Granite and return the generated text."""
        if self._initialized and self._model:
            return self._live_generate(prompt, max_tokens)
        return self._stub_generate(prompt)

    def match_grants_to_startup(self, startup_profile: dict, grants: list[dict]) -> list[dict]:
        """
        Use Granite to score and rank grants against a startup profile.
        Returns grants list sorted by AI relevance score (0–100).
        """
        if not grants:
            return []

        startup_summary = self._profile_to_text(startup_profile)
        scored = []

        for grant in grants[:20]:          # cap to avoid excessive token use
            prompt = self._build_matching_prompt(startup_summary, grant)
            raw = self.generate(prompt, max_tokens=200)
            score, reason = self._parse_score_response(raw)
            scored.append({**grant, "ai_score": score, "match_reason": reason})

        scored.sort(key=lambda g: g["ai_score"], reverse=True)
        return scored

    def generate_proposal(self, startup_profile: dict, grant: dict) -> str:
        """Draft a funding proposal for a specific grant using Granite."""
        prompt = self._build_proposal_prompt(startup_profile, grant)
        return self.generate(prompt, max_tokens=1024)

    def summarize_grant(self, grant_text: str) -> str:
        """Produce a concise summary of raw grant HTML/text."""
        prompt = (
            "You are a funding analyst. Read the following grant information and produce "
            "a concise 3-sentence summary covering: (1) purpose, (2) eligibility, "
            "(3) deadline and funding amount.\n\n"
            f"Grant Text:\n{grant_text[:3000]}\n\n"
            "Summary:"
        )
        return self.generate(prompt, max_tokens=300)

    def extract_eligibility(self, grant_text: str) -> dict:
        """Extract structured eligibility criteria from raw grant text."""
        prompt = (
            "Extract eligibility criteria from the grant text below. "
            "Return a JSON object with keys: startup_stage (list), "
            "sectors (list), geography (list), funding_range (string), "
            "special_requirements (list).\n\n"
            f"Grant Text:\n{grant_text[:2000]}\n\nJSON:"
        )
        raw = self.generate(prompt, max_tokens=400)
        return self._safe_parse_json(raw)

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_matching_prompt(self, startup_summary: str, grant: dict) -> str:
        return (
            "You are a funding advisor. Score how well this grant matches the startup "
            "(0 = no match, 100 = perfect match). Reply with JSON: "
            '{"score": <number>, "reason": "<one sentence>"}\n\n'
            f"Startup:\n{startup_summary}\n\n"
            f"Grant: {grant.get('title', '')}\n"
            f"Description: {grant.get('description', '')[:500]}\n"
            f"Eligibility: {grant.get('eligibility', '')[:300]}\n\n"
            "JSON Response:"
        )

    def _build_proposal_prompt(self, startup_profile: dict, grant: dict) -> str:
        return (
            "You are an expert grant writer. Draft a compelling funding proposal "
            "for the startup described below, tailored to the specific grant opportunity.\n\n"
            f"Startup Name: {startup_profile.get('name', 'Our Startup')}\n"
            f"Domain: {startup_profile.get('domain', '')}\n"
            f"Stage: {startup_profile.get('stage', '')}\n"
            f"Problem Solved: {startup_profile.get('problem', '')}\n"
            f"Solution: {startup_profile.get('solution', '')}\n"
            f"Location: {startup_profile.get('location', '')}\n"
            f"Team Size: {startup_profile.get('team_size', '')}\n\n"
            f"Grant: {grant.get('title', '')}\n"
            f"Grant Description: {grant.get('description', '')[:600]}\n"
            f"Funding Amount: {grant.get('funding_amount', 'Not specified')}\n\n"
            "Write a structured proposal with sections: Executive Summary, "
            "Problem Statement, Proposed Solution, Expected Impact, "
            "Budget Justification, and Conclusion.\n\nProposal:"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _profile_to_text(profile: dict) -> str:
        return (
            f"Name: {profile.get('name', 'N/A')}, "
            f"Domain: {profile.get('domain', 'N/A')}, "
            f"Stage: {profile.get('stage', 'N/A')}, "
            f"Location: {profile.get('location', 'N/A')}, "
            f"Team: {profile.get('team_size', 'N/A')} people, "
            f"Problem: {profile.get('problem', 'N/A')}"
        )

    @staticmethod
    def _parse_score_response(raw: str) -> tuple[int, str]:
        """Parse JSON {"score": X, "reason": "..."} from Granite output."""
        import re, json
        try:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                data = json.loads(m.group())
                return int(data.get("score", 50)), data.get("reason", "")
        except Exception:
            pass
        # fallback — extract bare number
        nums = re.findall(r'\b(\d{1,3})\b', raw)
        score = int(nums[0]) if nums else 50
        return min(score, 100), raw[:120]

    @staticmethod
    def _safe_parse_json(raw: str) -> dict:
        import re, json
        try:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception:
            pass
        return {}

    # ------------------------------------------------------------------
    # Stub (no credentials)
    # ------------------------------------------------------------------

    @staticmethod
    def _stub_generate(prompt: str) -> str:
        """Rule-based stub so the UI works without live IBM credentials."""
        prompt_lower = prompt.lower()
        if "proposal" in prompt_lower:
            return (
                "**Executive Summary**\n"
                "Our startup addresses a critical market gap with an innovative, "
                "technology-driven solution that aligns with the grant objectives.\n\n"
                "**Problem Statement**\n"
                "The current landscape lacks accessible, affordable solutions for the "
                "identified problem, affecting thousands of potential beneficiaries.\n\n"
                "**Proposed Solution**\n"
                "We propose a scalable platform leveraging AI and cloud technologies "
                "to deliver measurable impact at reduced cost.\n\n"
                "**Expected Impact**\n"
                "Projected to serve 10,000+ users within 18 months of funding.\n\n"
                "**Budget Justification**\n"
                "Funds will be allocated to R&D (40%), team expansion (35%), "
                "and market outreach (25%).\n\n"
                "**Conclusion**\n"
                "This grant will be a pivotal enabler in transforming our prototype "
                "into a production-ready solution with nationwide impact."
            )
        if "score" in prompt_lower or "match" in prompt_lower:
            return '{"score": 72, "reason": "Strong domain alignment with grant objectives."}'
        if "summary" in prompt_lower:
            return (
                "This grant supports early-stage startups in technology and innovation sectors. "
                "Eligible applicants must be registered entities with a working prototype. "
                "The deadline is rolling and funding ranges from ₹5L to ₹50L."
            )
        return "IBM Granite AI is ready. Please configure IBM_API_KEY in .env to enable live responses."
