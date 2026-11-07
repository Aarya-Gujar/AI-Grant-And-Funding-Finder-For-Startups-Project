"""
Proposal Generator — uses IBM Granite to draft tailored grant proposals.
"""

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class ProposalGenerator:
    """
    Generates funding proposals using IBM Granite AI.
    Falls back to structured templates when AI is unavailable.
    """

    def __init__(self, granite_service):
        self._granite = granite_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, startup_profile: dict, grant: dict) -> dict:
        """
        Generate a complete proposal for a startup + grant pairing.
        Returns a dict with: title, sections (list), metadata.
        """
        try:
            raw_text = self._granite.generate_proposal(startup_profile, grant)
            sections = self._parse_sections(raw_text)
            if not sections:
                # Granite returned unstructured text — wrap it
                sections = [{"heading": "Proposal", "content": raw_text}]
        except Exception as exc:
            logger.warning("AI proposal generation failed: %s — using template", exc)
            sections = self._template_proposal(startup_profile, grant)

        return {
            "title": f"Grant Proposal: {grant.get('title', 'Funding Opportunity')}",
            "startup": startup_profile.get("name", "Applicant Startup"),
            "grant_id": grant.get("id", ""),
            "grant_title": grant.get("title", ""),
            "funding_amount": grant.get("funding_amount", ""),
            "generated_at": datetime.utcnow().isoformat(),
            "sections": sections,
            "disclaimer": (
                "This proposal draft was AI-generated using IBM Granite. "
                "Review all facts, figures, and claims before submission. "
                "Ensure compliance with the grant authority's specific guidelines."
            ),
        }

    def generate_cover_letter(self, startup_profile: dict, grant: dict) -> str:
        """Generate a brief cover letter for the application."""
        prompt = (
            "Write a professional 3-paragraph cover letter from a startup "
            "applying for the following grant. Be concise and compelling.\n\n"
            f"Startup: {startup_profile.get('name', 'Our Company')}\n"
            f"Domain: {startup_profile.get('domain', '')}\n"
            f"Problem: {startup_profile.get('problem', '')}\n"
            f"Grant: {grant.get('title', '')}\n"
            f"Amount: {grant.get('funding_amount', '')}\n\n"
            "Cover Letter:"
        )
        return self._granite.generate(prompt, max_tokens=500)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_sections(text: str) -> list[dict]:
        """Extract markdown-style headings (##, **Heading**) into sections."""
        sections = []
        # Match ** bold headings ** or ## headings
        pattern = re.compile(
            r"(?:\*\*([^*]+)\*\*|##\s*([^\n]+))\n(.*?)(?=\*\*[^*]+\*\*|##\s|$)",
            re.DOTALL,
        )
        for m in pattern.finditer(text):
            heading = (m.group(1) or m.group(2)).strip()
            content = m.group(3).strip()
            if heading and content:
                sections.append({"heading": heading, "content": content})

        if not sections:
            # No headings — split by double newlines
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for i, para in enumerate(paragraphs):
                sections.append({"heading": f"Section {i + 1}", "content": para})
        return sections

    # ------------------------------------------------------------------
    # Template fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _template_proposal(startup_profile: dict, grant: dict) -> list[dict]:
        name = startup_profile.get("name", "Our Startup")
        domain = startup_profile.get("domain", "technology")
        problem = startup_profile.get("problem", "a critical market gap")
        solution = startup_profile.get("solution", "an innovative AI-driven platform")
        stage = startup_profile.get("stage", "early-stage")
        location = startup_profile.get("location", "India")
        team = startup_profile.get("team_size", "5")
        grant_title = grant.get("title", "this grant")
        amount = grant.get("funding_amount", "the requested funding")

        return [
            {
                "heading": "Executive Summary",
                "content": (
                    f"{name} is a {stage} {domain} startup based in {location}. "
                    f"We are applying for {grant_title} to accelerate the development "
                    f"and deployment of our solution addressing {problem}. "
                    f"This grant of {amount} will enable us to achieve key milestones "
                    f"within 12 months and create measurable social and economic impact."
                ),
            },
            {
                "heading": "Problem Statement",
                "content": (
                    f"The challenge we address: {problem}. "
                    f"This affects millions of people and remains underserved by current market solutions. "
                    f"Our research and user discovery in {location} confirm the urgency and scale of this problem."
                ),
            },
            {
                "heading": "Proposed Solution",
                "content": (
                    f"We propose {solution}. "
                    f"Built on a robust technology stack leveraging AI and cloud infrastructure (IBM Cloud), "
                    f"our solution is scalable, secure, and designed for accessibility. "
                    f"We have already validated the concept with early users and achieved initial traction."
                ),
            },
            {
                "heading": "Expected Impact",
                "content": (
                    f"Within 18 months, {name} aims to: (1) onboard 10,000+ users, "
                    f"(2) create {int(str(team or 5)) * 3}+ direct employment opportunities, "
                    f"(3) demonstrate measurable improvement in the target metric by 40%, "
                    f"(4) publish findings to contribute to the open knowledge ecosystem."
                ),
            },
            {
                "heading": "Budget Justification",
                "content": (
                    f"The requested {amount} will be allocated as follows: "
                    f"40% R&D and product development, "
                    f"30% team hiring and capacity building, "
                    f"20% market entry and customer acquisition, "
                    f"10% operations, compliance, and overheads. "
                    f"All expenditure will be documented and audited per grant guidelines."
                ),
            },
            {
                "heading": "Team",
                "content": (
                    f"{name} is led by a passionate team of {team} professionals with deep expertise "
                    f"in {domain}. Our founders bring a combination of technical depth, "
                    f"domain knowledge, and entrepreneurial experience essential for executing this vision."
                ),
            },
            {
                "heading": "Conclusion",
                "content": (
                    f"We believe {grant_title} is the ideal catalyst for {name} to accelerate growth "
                    f"and create lasting impact in the {domain} space. "
                    f"We are committed to transparent reporting, milestone-driven execution, "
                    f"and responsible use of public funds. We look forward to partnering with "
                    f"the grant authority to build a better tomorrow."
                ),
            },
        ]
