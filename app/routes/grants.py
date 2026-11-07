"""
Flask REST API routes — Grants endpoints
"""

import logging
from flask import Blueprint, request, jsonify
from app.services import GraniteAIService, GrantAggregator, MatchingEngine, ProposalGenerator

logger = logging.getLogger(__name__)
grants_bp = Blueprint("grants", __name__, url_prefix="/api/grants")

# Singletons (initialised once per process)
_granite = GraniteAIService()
_aggregator = GrantAggregator()
_matcher = MatchingEngine(granite_service=_granite)
_proposer = ProposalGenerator(granite_service=_granite)


# ── GET /api/grants ───────────────────────────────────────────────────────────

@grants_bp.route("", methods=["GET"])
def list_grants():
    """
    List / search grants.
    Query params:
      q           — keyword search
      domain      — comma-separated domains
      stage       — comma-separated stages
      location    — country / region string
      type        — funding type substring
      page        — page number (default 1)
      per_page    — results per page (default 20)
      refresh     — 'true' to force cache refresh
    """
    q = request.args.get("q", "").strip()
    domains = [d.strip() for d in request.args.get("domain", "").split(",") if d.strip()]
    stages = [s.strip() for s in request.args.get("stage", "").split(",") if s.strip()]
    location = request.args.get("location", "").strip()
    funding_type = request.args.get("type", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(1, int(request.args.get("per_page", 20))))
    force_refresh = request.args.get("refresh", "").lower() == "true"

    grants = _aggregator.search_grants(
        query=q,
        domains=domains or None,
        stages=stages or None,
        location=location,
        funding_type=funding_type,
    )
    if force_refresh:
        _aggregator.get_all_grants(force_refresh=True)
        grants = _aggregator.search_grants(query=q, domains=domains, stages=stages,
                                            location=location, funding_type=funding_type)

    total = len(grants)
    start = (page - 1) * per_page
    page_grants = grants[start: start + per_page]

    return jsonify({
        "status": "ok",
        "total": total,
        "page": page,
        "per_page": per_page,
        "grants": page_grants,
    })


# ── GET /api/grants/<id> ──────────────────────────────────────────────────────

@grants_bp.route("/<grant_id>", methods=["GET"])
def get_grant(grant_id):
    grant = _aggregator.get_grant_by_id(grant_id)
    if not grant:
        return jsonify({"status": "error", "message": "Grant not found"}), 404
    return jsonify({"status": "ok", "grant": grant})


# ── POST /api/grants/match ────────────────────────────────────────────────────

@grants_bp.route("/match", methods=["POST"])
def match_grants():
    """
    AI-powered grant matching.
    Body JSON:
      startup_profile: {
        name, domain, problem, solution, stage, location, team_size, keywords
      }
      use_ai: bool (default true)
      top_n:  int  (default 10)
    """
    data = request.get_json(silent=True) or {}
    profile = data.get("startup_profile", {})
    use_ai = data.get("use_ai", True)
    top_n = min(30, max(1, int(data.get("top_n", 10))))

    if not profile:
        return jsonify({"status": "error", "message": "startup_profile is required"}), 400

    all_grants = _aggregator.get_all_grants()
    ranked = _matcher.rank_grants(profile, all_grants, use_ai=use_ai, top_n=top_n)

    return jsonify({
        "status": "ok",
        "startup": profile.get("name", ""),
        "total_matched": len(ranked),
        "grants": ranked,
    })


# ── POST /api/grants/propose ──────────────────────────────────────────────────

@grants_bp.route("/propose", methods=["POST"])
def generate_proposal():
    """
    Generate an AI-drafted grant proposal.
    Body JSON:
      startup_profile: { name, domain, problem, solution, stage, location, team_size }
      grant_id:        string
    """
    data = request.get_json(silent=True) or {}
    profile = data.get("startup_profile", {})
    grant_id = data.get("grant_id", "")

    if not profile or not grant_id:
        return jsonify({
            "status": "error",
            "message": "startup_profile and grant_id are required",
        }), 400

    grant = _aggregator.get_grant_by_id(grant_id)
    if not grant:
        return jsonify({"status": "error", "message": "Grant not found"}), 404

    proposal = _proposer.generate(profile, grant)
    cover = _proposer.generate_cover_letter(profile, grant)
    proposal["cover_letter"] = cover

    return jsonify({"status": "ok", "proposal": proposal})


# ── POST /api/grants/summarize ────────────────────────────────────────────────

@grants_bp.route("/summarize", methods=["POST"])
def summarize_grant():
    """
    Summarise raw grant text using IBM Granite NLU.
    Body JSON: { "text": "<raw grant content>" }
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"status": "error", "message": "text is required"}), 400

    summary = _granite.summarize_grant(text)
    eligibility = _granite.extract_eligibility(text)

    return jsonify({
        "status": "ok",
        "summary": summary,
        "eligibility": eligibility,
    })
