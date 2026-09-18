# Reviewed edits — applied through Align APIs

facts.json is a list of {id, patch} for PATCH /api/demos/dm_36d47b86/align/facts/{id}. Every patch includes value for compatibility with the current API contract. Truth/source editing and C-fact lookup must be available before application. Source fields use ref, locator and quote.

approvals.json is a list of {id, patch} for POST /api/demos/dm_36d47b86/align/facts/{id}/approval. Send each patch as the body. It rejects C2-003 in favour of C4-003/004, rejects C2-015 in favour of C5-010, and holds C2-007 pending engine-specific evidence.

facts-provenance.json records the input fingerprint, original facts, intended patches and separately cited applicability evidence. It is an audit sidecar, not an API payload. C-fact primary source groups are unchanged. Source quotes remain exact source wording; conditions added from another original are identified as such in this sidecar. F030 retains camera/BVM and omits the separate front sensor. F031 uses a self-contained brochure feature/terms citation and omits the separately sourced 70+ count. F025 needs no correction.

validation.json records schema and new-quote checks. Preparation performed no API requests. Root applied the reviewed payloads through Align APIs; applied.json records the requests. Downstream approval and voiced Build remain pending.

iteration-2-addenda contains three concise reviewer transcriptions of official PDFs and provenance.json. Keep the Nexon source role product and the Brezza/Venue roles competitor; retain exact official origin URLs. These files add evidence for the next extraction, not direct fact IDs. They have not been uploaded or ingested.

plan-patch-01/02.json, script-patch.json and deck-patch.json correct the generated pitch and preserve the existing IDs. The cockpit picture/text/drag exercise was performed in the actual Studio UI; sl04-c1 coordinates remain x=0.0401, y=0.0453. ctas.json uses destinations present in the official source pages. The FAQ bank is being refreshed before approval.
