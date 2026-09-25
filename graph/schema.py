"""Explicit ontology shared by validation, export and Neo4j import."""

FORMAT_VERSION = 1
DATASET = "psu_dealing_mock"
GROUP_LABELS = {
    "hobbies": "Hobby", "traits": "Trait", "comm_styles": "CommStyle",
    "attachment_styles": "Attachment", "love_languages": "LoveLanguage",
    "love_components": "LoveComponent", "red_flags": "RedFlag",
    "research_factors": "ResearchFactor",
}
CONCEPT_LABELS = set(GROUP_LABELS.values())
FEATURE_LABELS = {"Trait", "CommStyle", "Attachment"}
LABELS = CONCEPT_LABELS | {"User", "Source", "BookChunk"}
# Domain/range checks are application-side; Neo4j uniqueness alone is insufficient.
RELATIONS = {
    "HAS_TRAIT": ({"User"}, FEATURE_LABELS),
    "LIKES": ({"User"}, {"Hobby"}),
    "HAS_LOVE_LANGUAGE": ({"User"}, {"LoveLanguage"}),
    "HAS_LOVE_COMPONENT": ({"User"}, {"LoveComponent"}),
    "HAS_FACTOR": ({"User"}, {"ResearchFactor"}),
    "PREFERS": ({"User"}, {"Trait"}),
    "AVOIDS": ({"User"}, {"RedFlag"}),
    "REPORTED_AS": ({"User"}, {"RedFlag"}),
    "UNMATCHED": ({"User"}, {"User"}),
    "MATCHED": ({"User"}, {"User"}),
    "PASSED": ({"User"}, {"User"}),
    "COMPATIBLE_WITH": (CONCEPT_LABELS, CONCEPT_LABELS),
    "CONFLICTS_WITH": (CONCEPT_LABELS, CONCEPT_LABELS),
    "OPPOSITE_OF": (CONCEPT_LABELS, CONCEPT_LABELS),
    "HAS_CHUNK": ({"Source"}, {"BookChunk"}),
    "ABOUT": ({"BookChunk"}, CONCEPT_LABELS),
}
EVENT_RELATIONS = {"unmatch": "UNMATCHED", "matched": "MATCHED", "pass": "PASSED"}
RULE_RELATIONS = {"COMPATIBLE_WITH", "CONFLICTS_WITH", "OPPOSITE_OF"}


def pick(obj, keys):
    """Use allowlists instead of copying arbitrary input properties."""
    return {key: obj[key] for key in keys if key in obj and obj[key] is not None}
