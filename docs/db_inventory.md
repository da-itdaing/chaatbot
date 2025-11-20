# Itdaing DB Inventory (Chatbot Focus)

## 1. Connection Summary
- Database: `itdaing-db`
- Extensions: `plpgsql`, `vector 0.8.0` (installed in `public` schema)
- Schemas observed: `public` (+ system schemas)

## 2. Key Tables & Notes

| Domain | Table | Key Columns / Notes | Row Count (2025-11-20) |
| --- | --- | --- | --- |
| Users | `users` | role-based users (CONSUMER/SELLER/ADMIN), unique `login_id`/`email` | 162 total / 106 sellers / 50 consumers |
| Seller Profile | `seller_profile` | one-to-one with `users.id`; holds category, region, contact info | 106 |
| Locations | `zone_area`, `zone_cell`, `zone_availability` | zone areas (regions) -> cells -> availability windows (with price, slots) | zone_cell sample: labels A1/A2..., `status=APPROVED` |
| Popups | `popup` + `popup_category/feature/style/image` | seller-submitted popups tied to zone cells; approval workflow + view counts | 149 |
| Consumer Reco | `daily_consumer_recommendation` | unique (consumer_id, date, popup_id); `model_version` & score, reason JSON | 24 |
| Seller Reco | `daily_seller_recommendation` | unique (seller_id, date, zone_area_id); currently 0 rows | 0 |
| Preferences | `user_pref_category/feature/region/style` | unique combos for personalization | populated (counts TBD) |
| Messaging | `message_thread`, `message`, `message_attachment` | seller↔admin messaging threads (subject, unread counts); attachments stored w/ S3 URLs | 2 threads / 3 messages |
| Guardrails | `guardrail_policy` | service-area-level forbidden keywords/topics | 1 row (광주광역시) |
| Event Log | `event_log`, `event_log_category` | user/popup/zone events with action types (VIEW/FAVORITE/etc.) | size TBD |
| Announcements | `announcement` | admin/seller notifications; optional popup association | active |
| Chatbot Prompts | `chatbot_prompt`, `chatbot_prompt_embedding` | internal prompt library + ivfflat index (vector(1536)) | 2 prompts / 168 embeddings |
| LangChain Store | `langchain_pg_collection`, `langchain_pg_embedding` | `itdaing_popups` + `my_docs` collections; embeddings stored as vector + JSON metadata | 2 collections / 168 embeddings |

## 3. Observations & Opportunities

1. **Consumer & Seller Data Readiness**
   - Popups already normalized by categories/features/styles and tied to `zone_cell` geometry. Perfect for LangGraph retrieval + RAG grounding.
   - `daily_consumer_recommendation` contains model scores and reasons; can be surfaced via chatbot ("오늘 추천").
   - Seller-facing data (`zone_area`, `zone_availability`, `daily_seller_recommendation`) enables "어디에 입점 가능?" flows once populated.

2. **Chatbot Content Sources**
   - `chatbot_prompt*` + `langchain_pg_*` already host vectorized documents (prompt_id `itdaing_popups` aligns with 168 chunks). No migration needed beyond verifying upserts when data changes.
   - `guardrail_policy` provides direct hook for moderation middleware (LangChain guardrails or FastAPI checks).

3. **Gaps / Recommended Additions**
   - **Chat session logging**: create `chatbot.chat_sessions` & `chatbot.chat_messages` tables (as described in `CHATBOT_DB.md`) to persist user-bot conversations separate from seller-admin inbox.
   - **Seller recommendation data**: table exists but empty; populate via ETL or inference pipeline so SELLER chatbot answers have actual suggestions.
   - **Analytics view**: consider materialized view or table linking `event_log` with `daily_consumer_recommendation` for feedback loops.
   - **Attachment metadata**: `message_attachment` stores S3 key; reuse schema when chatbot generates files (e.g., itinerary PDFs) to keep audit trail consistent.

4. **Indexes & Performance**
   - ivfflat index already configured on `chatbot_prompt_embedding.embedding` (lists=100). Ensure `SET ivfflat.probes` is tuned (via session config) for desired recall.
   - `langchain_pg_embedding` uses JSONB GIN index for metadata filtering. When storing additional tags (seller_id, zone_id), keep them in `cmetadata` JSON to leverage same index.

## 4. Proposed Schema Updates

```sql
-- Chat session log (consumer/seller chatbot)
CREATE TABLE chatbot.chat_sessions (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    bot_type VARCHAR(20) NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_message_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB
);

CREATE TABLE chatbot.chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chatbot.chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- USER | ASSISTANT | SYSTEM
    content TEXT NOT NULL,
    meta JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chat_messages_session ON chatbot.chat_messages(session_id, created_at);
```

- Optionally add `chatbot.chat_sessions.bot_type` FK to an enum table if governance is needed.
- For SELLER insights, add `seller_profile_metrics` table (seller_id, zone_area_id, avg_score, last_recommendation_at) if aggregations are required frequently.

## 5. Validation Steps
- Re-run `./scripts/vector_smoke_test.py` after any change affecting embeddings to confirm RDS connectivity.
- Use `psql -c "SELECT count(*) FROM chatbot.chat_sessions"` etc. to monitor chat log growth.
- Add Flyway/Liquibase migration entries when introducing new `chatbot.*` tables so Java/Spring services can evolve in lockstep.

---
_Last updated: 2025-11-20_
