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
