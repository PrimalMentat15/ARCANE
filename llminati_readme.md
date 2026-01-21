# The LLMinati

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://reactjs.org/)

> **Where AI minds converge, knowledge illuminates, and collective intelligence reigns supreme.**

![The LLMinati Header](header.png)

---

## Abstract

**The LLMinati** is a revolutionary AI research and deliberation platform that combines the collective intelligence of multi-model LLM councils with the structured knowledge management capabilities of Google NotebookLM. By orchestrating deliberations among diverse AI models while grounding their reasoning in curated research sources, The LLMinati transcends the limitations of single-model AI assistants and creates a new paradigm for AI-augmented research, analysis, and decision-making.

The platform enables users to:
- **Convene councils** of AI models (GPT-4, Claude, Gemini, Llama, etc.) that deliberate, peer-review, and synthesize responses
- **Ground deliberations** in structured research notebooks with sources from web, Google Drive, PDFs, and URLs
- **Generate rich outputs** including audio podcasts, video overviews, slide decks, and infographics
- **Maintain source citations** throughout the entire deliberation process for full transparency and traceability
- **Iterate research** through multi-stage pipelines that combine discovery, analysis, and content generation

---

## Project Goals

### Primary Objectives

1. **Collective AI Intelligence**: Harness diverse perspectives from multiple LLM providers to produce more balanced, comprehensive, and accurate insights than any single model could provide.

2. **Knowledge-Grounded Reasoning**: Ensure all AI deliberations are anchored in verified sources, reducing hallucinations and increasing trustworthiness.

3. **Enterprise-Ready Research Workflows**: Create production-grade tools for research teams, product managers, legal analysts, and content creators who need AI assistance with complex analytical tasks.

4. **Seamless Integration**: Unify LLM Council Plus and NotebookLM MCP into a cohesive platform without sacrificing the modularity of either system.

5. **Democratized AI Power**: Make advanced multi-model AI accessible through an intuitive interface that doesn't require technical expertise.

### Success Metrics

- **Response Quality**: 40%+ improvement in user satisfaction vs. single-model responses (measured via blind A/B testing)
- **Source Accuracy**: 90%+ of factual claims traceable to cited sources
- **Adoption**: 1,000+ active users within 6 months of launch
- **Use Case Diversity**: Platform used across 5+ distinct professional domains (research, legal, engineering, marketing, education)

---

## Proposed Architecture

### System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                        THE LLMINATI                                │
│                   (Unified Orchestration Layer)                    │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    Council Engine                         │    │
│  │  • Multi-model deliberation (Stage 1)                     │    │
│  │  • Anonymous peer review (Stage 2)                        │    │
│  │  • Chairman synthesis (Stage 3)                           │    │
│  │  • Temperature & execution mode controls                  │    │
│  └──────────────┬───────────────────────────┬────────────────┘    │
│                 │                           │                      │
│     ┌───────────▼──────────┐    ┌──────────▼────────────┐        │
│     │  Knowledge Engine    │    │  LLM Provider Hub     │        │
│     │  (NotebookLM MCP)    │    │  • OpenRouter         │        │
│     │                      │    │  • Ollama (Local)     │        │
│     │  • Notebook CRUD     │    │  • Groq               │        │
│     │  • Source ingestion  │    │  • OpenAI Direct      │        │
│     │  • AI summaries      │    │  • Anthropic Direct   │        │
│     │  • Web/Drive research│    │  • Google Direct      │        │
│     │  • Content generation│    │  • Mistral Direct     │        │
│     └──────────┬───────────┘    │  • DeepSeek Direct    │        │
│                │                 │  • Custom Endpoints   │        │
│                │                 └───────────────────────┘        │
│                │                                                   │
│     ┌──────────▼────────────────────────────────────────┐        │
│     │         External Integrations                     │        │
│     │                                                    │        │
│     │  ┌─────────────┐  ┌──────────────┐  ┌──────────┐ │        │
│     │  │ Google      │  │ Web Search   │  │ Jina     │ │        │
│     │  │ NotebookLM  │  │ • DuckDuckGo │  │ Reader   │ │        │
│     │  │ API         │  │ • Tavily     │  │          │ │        │
│     │  │             │  │ • Brave      │  │          │ │        │
│     │  └─────────────┘  └──────────────┘  └──────────┘ │        │
│     └───────────────────────────────────────────────────┘        │
└────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────────────┐
         │            User Interface Layer               │
         │                                               │
         │  • React 19 Frontend (Vite)                   │
         │  • FastAPI Backend                            │
         │  • Real-time streaming (SSE)                  │
         │  • Markdown rendering                         │
         │  • Conversation persistence (JSON)            │
         │  • Settings management                        │
         └───────────────────────────────────────────────┘
```

### Data Flow Architecture

```
User Query → Knowledge Enrichment → Council Deliberation → Synthesis → Output
     │              │                       │                  │          │
     │              ▼                       ▼                  ▼          ▼
     │     NotebookLM Search      Stage 1: Models      Stage 3:    Citations
     │     Source Extraction       Respond            Chairman      Podcast
     │     Drive Integration      Stage 2: Peer      Synthesis     Slides
     │                             Review                          Docs
     └──────────────────────────────────────────────────────────────────────┘
                            Persistent Notebooks (Google NotebookLM)
```

---

## Technologies Implemented

### Backend Stack

| Technology | Purpose | Version |
|------------|---------|---------|
| **Python** | Core backend language | 3.10+ |
| **FastAPI** | REST API server & WebSocket support | 0.115+ |
| **httpx** | Async HTTP client for LLM API calls | Latest |
| **uv** | Fast Python package manager | Latest |
| **MCP SDK** | Model Context Protocol integration | Latest |
| **YAKE** | Keyword extraction for smart search | Latest |

### Frontend Stack

| Technology | Purpose | Version |
|------------|---------|---------|
| **React** | UI framework | 19 |
| **Vite** | Build tool & dev server | Latest |
| **react-markdown** | Markdown rendering | Latest |
| **CSS3** | Custom "Midnight Glass" theme | - |

### LLM Integration

| Provider | Type | Access Method |
|----------|------|---------------|
| **OpenRouter** | Cloud | API (100+ models) |
| **Ollama** | Local | HTTP API |
| **Groq** | Cloud | API (ultra-fast inference) |
| **OpenAI** | Cloud | Direct API |
| **Anthropic** | Cloud | Direct API |
| **Google AI** | Cloud | Direct API |
| **Mistral** | Cloud | Direct API |
| **DeepSeek** | Cloud | Direct API |
| **Custom** | Any | OpenAI-compatible endpoint |

### Knowledge & Search

| Service | Purpose | Integration |
|---------|---------|-------------|
| **Google NotebookLM** | Document management, AI summaries, content generation | MCP Server |
| **DuckDuckGo** | Free web search | API |
| **Tavily** | LLM-optimized search | API |
| **Brave Search** | Privacy-focused search | API |
| **Jina Reader** | Full article extraction | API |
| **Google Drive** | Document storage/retrieval | NotebookLM MCP |

### Storage & Configuration

| Component | Technology | Location |
|-----------|------------|----------|
| **Settings** | JSON files | `data/settings.json` |
| **Conversations** | JSON files | `data/conversations/{uuid}.json` |
| **Auth Tokens** | JSON files | `~/.notebooklm-mcp/auth.json` |
| **Notebooks** | Cloud storage | Google NotebookLM servers |

---

## Development Plan

### Phase 1: Foundation Integration (Weeks 1-2)

**Goal**: Establish basic connectivity between LLM Council Plus and NotebookLM MCP

**Deliverables**:
- [ ] Fork and merge codebases into unified repository
- [ ] Add NotebookLM MCP as MCP client in Council backend
- [ ] Create "Notebook Mode" toggle in Council UI
- [ ] Enable council to query existing notebooks via MCP tools
- [ ] Test basic workflow: Create notebook → Add source → Council queries it
- [ ] Documentation: Installation guide, basic usage examples

**Technical Tasks**:
- Refactor Council backend to support MCP client connections
- Implement MCP tool discovery and invocation
- Add notebook selection UI component
- Create unified configuration system
- Set up development environment with both services

**Success Criteria**:
- User can select a notebook and ask council to analyze it
- Council receives source content from NotebookLM
- Basic error handling for MCP connection failures

---

### Phase 2: Bidirectional Workflow (Weeks 3-4)

**Goal**: Enable councils to create and update notebooks during deliberation

**Deliverables**:
- [ ] Council can create new notebooks automatically
- [ ] Auto-save council transcripts as NotebookLM text sources
- [ ] Import NotebookLM AI summaries into council context window
- [ ] Implement source citation tracking throughout deliberation
- [ ] Add "Research Mode" execution option
- [ ] Real-time notebook updates visible in UI

**Technical Tasks**:
- Implement notebook CRUD operations from council context
- Build citation extraction system for chairman synthesis
- Create source metadata management
- Add streaming updates for notebook changes
- Develop context window optimization for large sources

**Success Criteria**:
- Council automatically creates notebook for research queries
- Chairman synthesis includes source citations
- Users can see which sources influenced which council responses

---

### Phase 3: Advanced Research Pipelines (Weeks 5-8)

**Goal**: Build multi-stage research workflows with automated content generation

**Deliverables**:
- [ ] Smart source pre-filtering using council models
- [ ] Parallel research: NotebookLM + council web search
- [ ] Integrated deliverable generation (reports + audio/video)
- [ ] Drive-aware council deliberation
- [ ] Iterative research rounds with gap analysis
- [ ] Export system for final outputs

**Technical Tasks**:
- Implement multi-stage pipeline orchestration
- Build parallel execution engine for concurrent searches
- Integrate NotebookLM studio features (audio, video, slides)
- Add Google Drive search/import capabilities
- Create template system for research workflows
- Develop export functionality (PDF, Markdown, audio files)

**Success Criteria**:
- User triggers research → system autonomously discovers sources → council analyzes → generates podcast
- Council identifies knowledge gaps and requests additional research
- Complete research project exportable as comprehensive package

---

### Phase 4: UI/UX Unification (Weeks 9-12)

**Goal**: Create seamless single-interface experience

**Deliverables**:
- [ ] Unified dashboard showing councils + notebooks
- [ ] Drag-drop interface for adding sources to deliberations
- [ ] Real-time notebook updates during council sessions
- [ ] Enhanced visualization of deliberation stages
- [ ] Mobile-responsive design
- [ ] Onboarding flow for new users

**Technical Tasks**:
- Redesign frontend with unified navigation
- Implement drag-drop source management
- Build real-time sync system for notebook changes
- Create interactive deliberation visualizer
- Develop responsive CSS framework
- Add interactive tutorial system

**Success Criteria**:
- New users can complete first research project in <10 minutes
- No context switching between council and notebook interfaces
- Mobile users can review deliberations and notebooks

---

### Phase 5: Production Hardening (Weeks 13-16)

**Goal**: Make system production-ready for public launch

**Deliverables**:
- [ ] Comprehensive error handling and recovery
- [ ] Rate limiting and cost management
- [ ] Performance optimization (caching, lazy loading)
- [ ] Security audit and credential encryption
- [ ] Monitoring and logging infrastructure
- [ ] User authentication and multi-tenant support
- [ ] Docker containerization
- [ ] CI/CD pipeline

**Technical Tasks**:
- Implement retry logic and fallback mechanisms
- Add request queuing for API rate limits
- Build caching layer for frequent queries
- Encrypt API keys and auth tokens
- Set up Sentry/LogRocket for error tracking
- Implement user management system
- Create Dockerfile and docker-compose setup
- Configure GitHub Actions for automated testing

**Success Criteria**:
- 99.5% uptime over 1-week stress test
- API costs <$0.10 per deliberation on average
- All credentials encrypted at rest
- Zero security vulnerabilities in audit

---

### Phase 6: Advanced Features & Scale (Weeks 17-20)

**Goal**: Add power-user features and prepare for scale

**Deliverables**:
- [ ] Team workspaces with shared notebooks
- [ ] API endpoint for programmatic access
- [ ] Scheduled deliberations (cron jobs)
- [ ] Advanced analytics dashboard
- [ ] Custom council presets library
- [ ] Browser extension for quick access
- [ ] Mobile app (React Native)

**Technical Tasks**:
- Design multi-tenant database schema
- Build public API with authentication
- Implement job scheduling system
- Create analytics data pipeline
- Develop preset import/export system
- Build Chrome/Firefox extensions
- Port UI to React Native

**Success Criteria**:
- 10+ teams actively using shared workspaces
- API handles 1000+ requests/day
- Analytics show user engagement patterns
- Browser extension has 100+ installs

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- uv (Python package manager)
- Google account (for NotebookLM)
- API keys for at least one LLM provider

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/llminati.git
cd llminati

# Install backend dependencies
uv sync

# Install frontend dependencies
cd frontend
npm install
cd ..

# Authenticate with NotebookLM
notebooklm-mcp-auth

# Start the platform
./start.sh
```

Then open **http://localhost:5173** in your browser.

---

## Contributing

We embrace the spirit of "vibe coding" while striving for production quality. Contributions are welcome from developers of all skill levels.

**Areas where we need help**:
- Python optimization and best practices
- React performance improvements
- MCP server implementation expertise
- UX/UI design
- Documentation and tutorials
- Testing and QA

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Roadmap Beyond v1.0

- **Knowledge Graph Integration**: Connect related sources across notebooks
- **Fine-tuned Council Members**: Train specialized models for domain expertise
- **Voice Interface**: Speak to the council, hear audio responses
- **Collaborative Editing**: Multiple users deliberating simultaneously
- **Enterprise SSO**: SAML/OAuth integration for corporate deployments
- **Regulatory Compliance**: GDPR, HIPAA, SOC2 compliance certifications

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Acknowledgements

This project builds upon and integrates:
- **[LLM Council Plus](https://github.com/jacob-bd/llm-council-plus)** by jacob-bd (fork of llm-council by Andrej Karpathy)
- **[NotebookLM MCP](https://github.com/jacob-bd/notebooklm-mcp)** by jacob-bd

Special thanks to the open-source AI community for making this level of integration possible.

---

**Built with the collective wisdom of AI**  
*Where minds meet, knowledge emerges.*

🔺 **The LLMinati** 🔺
