// Run each block separately in Neo4j Browser. Always use the active snapshot.

// 1. Profile neighbourhood (change U001 to another user).
MATCH (d:DealingDataset {id:'psu_dealing_mock'})
MATCH (u:DealingEntity:User {dataset:d.id, snapshot:d.active_snapshot, id:'U001'})
MATCH (u)-[r]->(concept:Concept)
RETURN u, r, concept;

// 2. All 14 taxonomy rules. These are unverified project rules, not diagnoses.
MATCH (d:DealingDataset {id:'psu_dealing_mock'})
MATCH (a:DealingEntity:Concept {dataset:d.id, snapshot:d.active_snapshot})
      -[r:COMPATIBLE_WITH|CONFLICTS_WITH|OPPOSITE_OF]->(b:Concept)
RETURN a, r, b;

// 3. Document -> chunk -> concept, with pages/text on each chunk.
MATCH (d:DealingDataset {id:'psu_dealing_mock'})
MATCH p=(s:DealingEntity:Source {dataset:d.id, snapshot:d.active_snapshot})
        -[:HAS_CHUNK]->(c:BookChunk)-[:ABOUT]->(concept:Concept)
RETURN p LIMIT 100;

// 4. Reported behaviour + avoidance: inspect existing records, no matching score.
MATCH (d:DealingDataset {id:'psu_dealing_mock'})
MATCH (a:DealingEntity:User {dataset:d.id, snapshot:d.active_snapshot})
      -[avoid:AVOIDS]->(rf:RedFlag)<-[report:REPORTED_AS]-(b:User)
WHERE a <> b
RETURN a, avoid, rf, report, b LIMIT 30;

// 5. Inspect an explicit two-user path through a taxonomy rule.
MATCH (d:DealingDataset {id:'psu_dealing_mock'})
MATCH p=(a:DealingEntity:User {dataset:d.id, snapshot:d.active_snapshot, id:'U001'})
        -[:HAS_TRAIT]->(:Concept)-[:COMPATIBLE_WITH|CONFLICTS_WITH|OPPOSITE_OF]-(:Concept)
        <-[:HAS_TRAIT]-(b:DealingEntity:User {dataset:d.id, snapshot:d.active_snapshot, id:'U002'})
RETURN p;

// 6. Export all nodes in the active snapshot via Browser Table -> CSV / JSON.
// No LIMIT: verify the returned record count and Browser record limit.
MATCH (d:DealingDataset {id:'psu_dealing_mock'})
MATCH (n:DealingEntity {dataset:d.id, snapshot:d.active_snapshot})
RETURN n.id AS id, labels(n) AS labels, properties(n) AS properties
ORDER BY id;

// 7. Export all relationships in the active snapshot via Table -> CSV / JSON.
MATCH (d:DealingDataset {id:'psu_dealing_mock'})
MATCH (a:DealingEntity {dataset:d.id, snapshot:d.active_snapshot})-[r]->
      (b:DealingEntity {dataset:d.id, snapshot:d.active_snapshot})
RETURN r.id AS id, a.id AS source, type(r) AS relationship,
       b.id AS target, properties(r) AS properties
ORDER BY id;
