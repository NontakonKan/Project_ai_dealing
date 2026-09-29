"""Read-only graph inspection, without matching scores, ranking or RAG."""

QUERIES = {
    "claim-evidence": """
        MATCH (concept:DealingEntity:Concept {dataset:$dataset, snapshot:$snapshot, id:$concept_id})
              <-[role:SUBJECT|OBJECT]-(claim:Claim)-[:SUPPORTED_BY]->(chunk:BookChunk)
              <-[:HAS_CHUNK]-(source:Source)
        RETURN claim.id AS claim_id, type(role) AS matched_role,
               claim.assertion AS review_status, claim.predicate AS predicate,
               claim.polarity AS polarity, claim.qualifier_text AS qualifier,
               claim.text AS quote, chunk.id AS chunk_id, chunk.pages AS pages,
               source.source_id AS source_id, source.title AS title
        ORDER BY source_id, chunk_id, claim_id
    """,
    "claims": """
        MATCH (c:DealingEntity:Claim {dataset:$dataset, snapshot:$snapshot})
              -[:SUPPORTED_BY]->(b:BookChunk)
        OPTIONAL MATCH (c)-[:SUBJECT]->(subject:Concept)
        OPTIONAL MATCH (c)-[:OBJECT]->(obj:Concept)
        OPTIONAL MATCH (c)-[:ABOUT]->(t:Concept)
        WITH c, b, subject, obj, collect(DISTINCT t.id) AS concepts
        RETURN c.id AS claim_id, c.text AS quote, c.assertion AS status,
               subject.id AS subject_id, c.predicate AS predicate,
               obj.id AS object_concept_id, c.object_text AS object_text,
               c.polarity AS polarity, c.qualifier_text AS qualifier_text,
               c.reviewed_by AS reviewed_by, c.reviewed_at AS reviewed_at,
               b.id AS chunk_id, b.source_id AS source_id, concepts
        ORDER BY claim_id
    """,
    "summary": """
        MATCH (n:DealingEntity {dataset:$dataset, snapshot:$snapshot})
        UNWIND [label IN labels(n) WHERE NOT label IN ['DealingEntity', 'Concept']] AS label
        RETURN label, count(*) AS count ORDER BY label
    """,
    "profile": """
        MATCH (u:DealingEntity:User {dataset:$dataset, snapshot:$snapshot, id:$user_id})
        OPTIONAL MATCH (u)-[r]->(c:DealingEntity:Concept {dataset:$dataset, snapshot:$snapshot})
        RETURN u.id AS user_id, u.matching_consent AS matching_consent,
               type(r) AS relationship, c.id AS concept_id, c.label_th AS label,
               properties(r) AS evidence ORDER BY relationship, concept_id
    """,
    "events": """
        MATCH (u:DealingEntity:User {dataset:$dataset, snapshot:$snapshot, id:$user_id})
              -[e:UNMATCHED|MATCHED|PASSED]-
              (other:DealingEntity:User {dataset:$dataset, snapshot:$snapshot})
        RETURN e.event_id AS event_id, type(e) AS event_type,
               startNode(e).id AS from_user, endNode(e).id AS about_user,
               e.timestamp AS timestamp ORDER BY timestamp, event_id
    """,
    "shared": """
        MATCH (a:DealingEntity:User {dataset:$dataset, snapshot:$snapshot, id:$user_id})
              -[ar:HAS_TRAIT|LIKES|HAS_LOVE_LANGUAGE]->(c:Concept)
              <-[br:HAS_TRAIT|LIKES|HAS_LOVE_LANGUAGE]-
              (b:DealingEntity:User {dataset:$dataset, snapshot:$snapshot, id:$other_id})
        WHERE a <> b AND type(ar) = type(br)
        RETURN c.id AS concept_id, c.label_th AS label, type(ar) AS relationship,
               ar.confidence AS confidence_a, br.confidence AS confidence_b
        ORDER BY concept_id
    """,
    "rules": """
        MATCH (a:DealingEntity:Concept {dataset:$dataset, snapshot:$snapshot})
              -[r:COMPATIBLE_WITH|CONFLICTS_WITH|OPPOSITE_OF]->
              (b:DealingEntity:Concept {dataset:$dataset, snapshot:$snapshot})
        RETURN a.id AS from_concept, type(r) AS relationship, b.id AS to_concept,
               r.weight AS weight, r.reason AS reason, r.source AS source,
               r.assertion AS assertion, r.symmetric AS symmetric
        ORDER BY from_concept, relationship, to_concept
    """,
    "rule-paths": """
        MATCH (a:DealingEntity:User {dataset:$dataset, snapshot:$snapshot, id:$user_id})
              -[:HAS_TRAIT]->(x:Concept)
              -[r:COMPATIBLE_WITH|CONFLICTS_WITH|OPPOSITE_OF]-(y:Concept)
              <-[:HAS_TRAIT]-
              (b:DealingEntity:User {dataset:$dataset, snapshot:$snapshot, id:$other_id})
        WHERE a <> b
        RETURN DISTINCT a.id AS user_a, x.id AS concept_a, type(r) AS relationship,
               y.id AS concept_b, b.id AS user_b, r.weight AS weight,
               r.reason AS reason, r.source AS source, r.assertion AS assertion
        ORDER BY concept_a, relationship, concept_b
    """,
    "reports": """
        MATCH (u:DealingEntity:User {dataset:$dataset, snapshot:$snapshot})
              -[r:REPORTED_AS]->(c:RedFlag)
        RETURN u.id AS user_id, c.id AS concept_id, r.report_count AS report_count,
               r.assertion AS assertion ORDER BY user_id, concept_id
    """,
    "chunks": """
        MATCH (s:DealingEntity:Source {dataset:$dataset, snapshot:$snapshot})
              -[:HAS_CHUNK]->(c:BookChunk)-[tag:ABOUT]->
              (concept:DealingEntity:Concept {dataset:$dataset, snapshot:$snapshot, id:$concept_id})
        RETURN s.source_id AS source_id, s.title AS title, c.chunk_id AS chunk_id,
               c.pages AS pages, c.section_title AS section, c.text AS text,
               tag.assertion AS tag_status ORDER BY source_id, chunk_id
    """,
    # คำนวณ feature ของคู่ (A, B) ให้ตรงกับ graph/scorer.py (เวอร์ชันในหน่วยความจำ)
    "pair-features": """
        MATCH (a:DealingEntity:User {dataset:$dataset, snapshot:$snapshot, id:$user_id}),
              (b:DealingEntity:User {dataset:$dataset, snapshot:$snapshot, id:$other_id})
        OPTIONAL MATCH (a)-[:LIKES]->(h:Hobby)<-[:LIKES]-(b)
        WITH a, b, count(DISTINCT h) AS shared_hobbies
        OPTIONAL MATCH (a)-[:HAS_TRAIT]->(x)-[r:COMPATIBLE_WITH|CONFLICTS_WITH|OPPOSITE_OF]-(y)<-[:HAS_TRAIT]-(b)
        WITH a, b, shared_hobbies,
             sum(CASE type(r) WHEN 'COMPATIBLE_WITH' THEN r.weight WHEN NULL THEN 0 ELSE -r.weight END) AS theory_raw
        OPTIONAL MATCH (a)-[av:AVOIDS]->(rf:RedFlag)<-[rep:REPORTED_AS]-(b)
        RETURN shared_hobbies, theory_raw, collect(DISTINCT rf.id) AS red_flags_hit
    """,
}
