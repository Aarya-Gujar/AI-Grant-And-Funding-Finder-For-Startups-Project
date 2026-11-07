import sys, os
os.environ.setdefault('IBM_API_KEY', 'stub')
os.environ.setdefault('IBM_PROJECT_ID', 'stub')
os.environ.setdefault('IBM_WATSONX_URL', 'https://us-south.ml.cloud.ibm.com')
os.environ.setdefault('IBM_GRANITE_MODEL_ID', 'ibm/granite-13b-instruct-v2')
os.environ.setdefault('SECRET_KEY', 'test')

from app.services.grant_aggregator import GrantAggregator, STATIC_GRANTS
print("GrantAggregator OK - {} static grants loaded".format(len(STATIC_GRANTS)))

from app.services.matching_engine import MatchingEngine
me = MatchingEngine()
profile = {'name': 'TestAI', 'domain': 'AI', 'stage': 'early-stage', 'location': 'India', 'problem': 'test'}
ranked = me.rank_grants(profile, STATIC_GRANTS[:5], use_ai=False)
print("MatchingEngine OK - top grant: {} (score {})".format(ranked[0]['title'][:50], ranked[0]['relevance_score']))

from app.services.granite_service import GraniteAIService
g = GraniteAIService()
r = g.generate('test prompt for proposal')
print("GraniteAIService OK - stub mode: {}".format(r[:60]))

from app.services.proposal_generator import ProposalGenerator
pg = ProposalGenerator(g)
proposal = pg.generate(
    {'name': 'TestAI', 'domain': 'AI', 'stage': 'early-stage', 'location': 'India',
     'problem': 'x', 'solution': 'y', 'team_size': 4},
    STATIC_GRANTS[0]
)
print("ProposalGenerator OK - sections: {}".format(len(proposal['sections'])))

from app import create_app
app = create_app()
print("Flask app factory OK - registered blueprints: {}".format([b.name for b in app.blueprints.values()]))

print("\nAll smoke tests PASSED")
