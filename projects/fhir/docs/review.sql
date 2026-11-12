-- Quarantine impact by source feed and disposition.
SELECT batch.feed, resource.disposition, COUNT(*) AS entries
FROM resource JOIN batch USING (batch_id)
GROUP BY batch.feed, resource.disposition
ORDER BY batch.feed, resource.disposition;

-- Sources blocked solely by an upstream record, with target findings for triage.
SELECT b.source_file, edge.entry_index AS blocked_entry, edge.field, edge.target_index,
       t.resource_type AS target_type, f.rule_id AS target_rule, f.source_path
FROM reference AS edge
JOIN batch AS b USING (batch_id)
JOIN resource AS s ON s.batch_id = edge.batch_id AND s.entry_index = edge.entry_index
JOIN resource AS t ON t.batch_id = edge.batch_id AND t.entry_index = edge.target_index
JOIN finding AS f ON f.batch_id = t.batch_id AND f.entry_index = t.entry_index
JOIN rule AS r USING (rule_id)
WHERE s.disposition = 'dependent' AND t.disposition <> 'accepted' AND r.severity = 'error'
ORDER BY b.source_file, edge.entry_index, edge.target_index, f.rule_id
LIMIT 12;

-- Expected result is zero. This reconciles the published accepted graph.
SELECT COUNT(*) AS accepted_edges_with_quarantined_target
FROM reference AS edge
JOIN resource AS s ON s.batch_id = edge.batch_id AND s.entry_index = edge.entry_index
JOIN resource AS t ON t.batch_id = edge.batch_id AND t.entry_index = edge.target_index
WHERE s.disposition = 'accepted' AND t.disposition <> 'accepted';
