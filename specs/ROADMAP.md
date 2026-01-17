# DeniDin - Future Enhancements Roadmap

## Priority 0 (Critical)
- [ ] **002+007 - Memory System (Combined)** - Session management + ChromaDB long-term memory with semantic search. **MVP Phase 1**: Conversation history, `/remember` command, AI automatic recall, Godfather global memory. **Phase 2**: Per-chat memory, document ingestion (PDF/DOCX). (see `specs/002-007-memory-system/`)
- [ ] **006 - RBAC User Roles** - Role-based access control (ADMIN, GODFATHER, CLIENT, BLOCKED) with permission matrix (see `specs/006-rbac-user-roles/`)
- [ ] Implement rate limiting per user to prevent API cost overruns
- [ ] Add health check endpoint for monitoring

## Priority 1 (High)
- [ ] **003 - Media & Document Processing** - Support for images (GPT-4 Vision), PDFs (pdfplumber), DOCX files (python-docx) with AI analysis. **Note**: Document text extraction merged into 002+007 Phase 2 (see `specs/003-media-document-processing/`)
- [ ] **004 - MCP WhatsApp Server** - Model Context Protocol server for sending WhatsApp messages with contact resolution and fuzzy matching (see `specs/004-mcp-whatsapp-server/`)
- [ ] Multi-user conversation tracking with separate contexts
- [ ] Add admin commands (stats, restart, config reload)
- [ ] Metrics dashboard (message count, token usage, response times)

## Priority 2 (Medium)
- [ ] **005 - MCP Morning Green Receipt** - Integration with Morning's Israeli invoicing service (8 MCP tools, Hebrew support) (see `specs/005-mcp-morning-green-receipt/`)
- [ ] Support multiple AI models (Claude, Gemini, local LLMs)
- [ ] Custom AI personalities per user/group
- [ ] Integration with calendar services (Google Calendar, Outlook)
- [ ] Voice message transcription using Whisper API
- [ ] Text-to-speech for responses
- [ ] Webhook support for external integrations
- [ ] Plugin/extension system for custom handlers

## Priority 3 (Low/Future)
- [ ] **008 - Scheduled Proactive Chats** - System-initiated conversations on daily/weekly basis with 7 trigger types (cron, interval, event, condition) (see `specs/008-scheduled-proactive-chats/`)
- [ ] **009 - Agentic Workflow Builder** - Create complex multi-step workflows via natural language with AI decision-making (see `specs/009-agentic-workflow-builder/`)
- [ ] Multi-language support with auto-detection
- [ ] Sentiment analysis and emotion detection
- [ ] Integration with CRM systems (Salesforce, HubSpot)
- [ ] E-commerce capabilities (product search, order status)
- [ ] A/B testing framework for different prompts/models
- [ ] Web dashboard for configuration and analytics
- [ ] Mobile app for admin/monitoring
- [ ] Blockchain integration for message verification
- [ ] Integration with Slack, Telegram, Discord

## Ideas Backlog (Unprioritized)
- [ ] Add conversation history/context management (remember previous messages in conversation)
- [ ] Implement rate limiting per user to prevent API cost overruns
- [ ] Add health check endpoint for monitoring

## Priority 1 (High)
- [ ] Support media messages (images, voice notes, documents)
- [ ] Image analysis using GPT-4 Vision
- [ ] Multi-user conversation tracking with separate contexts
- [ ] Add admin commands (stats, restart, config reload)
- [ ] Metrics dashboard (message count, token usage, response times)
- [ ] PostgreSQL/Redis for persistent conversation storage

## Priority 2 (Medium)
- [ ] Support multiple AI models (Claude, Gemini, local LLMs)
- [ ] Custom AI personalities per user/group
- [ ] Scheduled messages and reminders
- [ ] Integration with calendar services (Google Calendar, Outlook)
- [ ] Voice message transcription using Whisper API
- [ ] Text-to-speech for responses
- [ ] Webhook support for external integrations
- [ ] Plugin/extension system for custom handlers

## Priority 3 (Low/Future)
- [ ] Multi-language support with auto-detection
- [ ] Sentiment analysis and emotion detection
- [ ] Integration with CRM systems (Salesforce, HubSpot)
- [ ] E-commerce capabilities (product search, order status)
- [ ] Knowledge base integration (RAG with vector databases)
- [ ] A/B testing framework for different prompts/models
- [ ] Web dashboard for configuration and analytics
- [ ] Mobile app for admin/monitoring
- [ ] Blockchain integration for message verification
- [ ] Integration with Slack, Telegram, Discord

## Ideas Backlog (Unprioritized)
- [ ] Automated testing with synthetic conversations
- [ ] Cost optimization with prompt caching
- [ ] Support for WhatsApp Business API features (templates, buttons, lists)
- [ ] Integration with payment providers (Stripe, PayPal)
- [ ] Email notifications for important events
- [ ] Backup and disaster recovery automation
- [ ] Multi-region deployment for lower latency
- [ ] GraphQL API for external integrations

---

**Last Updated**: January 17, 2026
**Current Version**: v1.0.0
