"""canonical topic taxonomy: merge AI-invented duplicate topics

ADR-056. Seeds the fixed taxonomy, moves every story and reader subscription
from a retired topic onto its canonical topic (a reader keeps the most
immediate urgency among the merged subscriptions), drops links to topics
with no canonical home, and deactivates every non-canonical topic.

The slug lists are a frozen copy of `app/content/topics.py` as of this
revision; later edits there do not change what this migration did.

Revision ID: f6a2c8e4b1d7
Revises: e5b9d3f7a2c4
Create Date: 2026-10-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a2c8e4b1d7"
down_revision: Union[str, None] = "e5b9d3f7a2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CANONICAL_TOPICS = [
    ("immigration", "Immigration"), ("andhra-pradesh", "Andhra Pradesh"), ("telangana", "Telangana"),
    ("hyderabad", "Hyderabad"), ("india", "India"), ("us-news", "US News"), ("world", "World"),
    ("politics", "Politics"), ("government", "Government & Welfare"), ("community", "NRI & Community"),
    ("entertainment", "Entertainment"), ("sports", "Sports"), ("money", "Money"), ("business", "Business"),
    ("jobs", "Jobs"), ("education", "Education"), ("property", "Property"), ("technology", "Technology"),
    ("health", "Health"), ("crime-safety", "Crime & Safety"), ("legal", "Courts & Legal"),
    ("agriculture", "Agriculture"), ("infrastructure", "Infrastructure"),
    ("environment", "Weather & Environment"), ("culture", "Culture & Religion"), ("travel", "Travel"),
    ("parents", "Parents"),
    ("f1", "F-1"), ("cpt", "CPT"), ("opt", "OPT"), ("stem-opt", "STEM OPT"),
    ("h1b-transition", "H-1B Transition"), ("internships", "Internships"),
    ("university-policy", "University Policy"), ("campus-safety", "Campus Safety"), ("taxes", "Taxes"),
    ("housing", "Housing"), ("scholarships", "Scholarships"), ("student-community", "Student Community"),
    ("international-student-jobs", "International Student Jobs"),
]

RETIRED = {
    "immigration": "immigration-visas us-immigration us-visas visa-updates us-immigration-diaspora immigration-education",
    "andhra-pradesh": "andhra-pradesh-news",
    "telangana": "telangana-news telangana-local-news telangana-politics",
    "india": "national national-news india-news defense",
    "us-news": "us-politics us-policy usa",
    "world": "international-news international-relations",
    "politics": "state-politics regional-politics elections local-elections state-elections politics-government "
    "government-politics politics-governance state-politics-governance protests public-protests water-disputes",
    "government": "state-government local-governance local-administration welfare-schemes governance "
    "state-governance social-welfare government-policy public-welfare state-government-schemes "
    "government-administration government-schemes government-services land-administration land-governance "
    "local-government policy regional-governance state-administration state-government-employees pensioners "
    "welfare housing-and-welfare cooperative-society land-acquisition land-issues appointments",
    "community": "nri-news nri nris diaspora diaspora-affairs telugu-diaspora community-events community-diaspora "
    "community-news community-development events local-events regional-events philanthropy success-story "
    "success-stories achievements awards awards-honors",
    "entertainment": "tollywood cinema telugu-cinema telugu-cinema-and-entertainment television movies ott "
    "movie-review movie-reviews box-office celebrity culture-entertainment interviews",
    "sports": "cricket",
    "money": "economy economy-finance finance market-updates consumer consumer-affairs consumer-news",
    "business": "business-economy local-industry startups economic-development women-entrepreneurs",
    "jobs": "employment labor labor-employment labor-and-employment labor-rights labor-welfare labor-issues career-jobs",
    "education": "jobs-education education-jobs",
    "property": "real-estate real-estate-housing housing-and-real-estate",
    "technology": "science-technology innovation cyber-security",
    "health": "healthcare health-fitness health-safety",
    "crime-safety": "crime accidents crime-and-accidents law-and-order local-crime-accidents police-and-crime "
    "accidents-disasters accidents-safety accidents-tragedies crime-accidents crime-atrocities crime-corruption "
    "crime-security crime-and-justice crime-justice law-order law-enforcement public-safety safety "
    "safety-security security society-safety tragedy fraud cybercrime corruption corruption-governance",
    "legal": "crime-courts crime-legal legal-governance legal-judiciary law-governance",
    "agriculture": "agriculture-irrigation",
    "infrastructure": "transport transportation infrastructure-development energy energy-infrastructure "
    "public-infrastructure infrastructure-utilities development state-development local-development "
    "civic-and-sanitation aviation water-resources",
    "environment": "weather natural-disasters",
    "culture": "religion history-culture arts-culture culture-heritage culture-religion devotional traditions "
    "religion-spirituality festivals heritage history culture-events culture-awards",
    "travel": "tourism",
    "taxes": "taxation",
}


def upgrade() -> None:
    conn = op.get_bind()
    for slug, name in CANONICAL_TOPICS:
        conn.execute(
            sa.text(
                "INSERT INTO topics (id, slug, name, active) VALUES (gen_random_uuid(), :slug, :name, true) "
                "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, active = true"
            ),
            {"slug": slug, "name": name},
        )

    op.execute("CREATE TEMP TABLE topic_merge (old_slug text PRIMARY KEY, new_slug text NOT NULL) ON COMMIT DROP")
    for new_slug, old_slugs in RETIRED.items():
        for old_slug in old_slugs.split():
            conn.execute(
                sa.text("INSERT INTO topic_merge (old_slug, new_slug) VALUES (:old, :new)"),
                {"old": old_slug, "new": new_slug},
            )

    op.execute(
        """
        INSERT INTO story_topics (story_id, topic_id, weight)
        SELECT st.story_id, n.id, max(st.weight)
        FROM story_topics st
        JOIN topics o ON o.id = st.topic_id
        JOIN topic_merge m ON m.old_slug = o.slug
        JOIN topics n ON n.slug = m.new_slug
        GROUP BY st.story_id, n.id
        ON CONFLICT (story_id, topic_id) DO NOTHING
        """
    )
    # Most immediate urgency wins: INSTANT, then BREAKING_ONLY, then DIGEST.
    op.execute(
        """
        INSERT INTO user_topics (user_id, topic_id, weight, urgency)
        SELECT DISTINCT ON (ut.user_id, n.id) ut.user_id, n.id, ut.weight, ut.urgency
        FROM user_topics ut
        JOIN topics o ON o.id = ut.topic_id
        JOIN topic_merge m ON m.old_slug = o.slug
        JOIN topics n ON n.slug = m.new_slug
        ORDER BY ut.user_id, n.id,
          CASE ut.urgency WHEN 'INSTANT' THEN 0 WHEN 'BREAKING_ONLY' THEN 1 ELSE 2 END
        ON CONFLICT (user_id, topic_id) DO UPDATE SET urgency = CASE
          WHEN (CASE EXCLUDED.urgency WHEN 'INSTANT' THEN 0 WHEN 'BREAKING_ONLY' THEN 1 ELSE 2 END)
             < (CASE user_topics.urgency WHEN 'INSTANT' THEN 0 WHEN 'BREAKING_ONLY' THEN 1 ELSE 2 END)
          THEN EXCLUDED.urgency ELSE user_topics.urgency END
        """
    )

    canonical = ", ".join(f"'{slug}'" for slug, _ in CANONICAL_TOPICS)
    op.execute(f"DELETE FROM story_topics WHERE topic_id IN (SELECT id FROM topics WHERE slug NOT IN ({canonical}))")
    op.execute(f"DELETE FROM user_topics WHERE topic_id IN (SELECT id FROM topics WHERE slug NOT IN ({canonical}))")
    op.execute(f"UPDATE topics SET active = false WHERE slug NOT IN ({canonical})")


def downgrade() -> None:
    # The merge is not reversible (merged links lose their original topic);
    # only the retired topics are made visible again.
    op.execute("UPDATE topics SET active = true")
