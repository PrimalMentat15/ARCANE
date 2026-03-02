# Local LLM Integration Guide for ARCANE

> **Goal:** Run ARCANE simulations entirely offline using locally-hosted LLMs (Llama 3, Qwen 2.5, Mistral, etc.) instead of cloud APIs (Gemini / OpenRouter).
>
> **Current Setup:** LM Studio with Meta Llama 3.1 8B Instruct

---

## Architecture Overview

ARCANE's LLM layer already uses a provider abstraction (`BaseProvider`). Adding local LLM support means creating a new provider class that talks to a local inference server instead of a cloud API. The rest of ARCANE (agents, channels, memory, prompts) stays untouched.

```
                Existing                              New
           ┌──────────────┐                    ┌────────────────┐
           │ GeminiProvider│                    │LocalLLMProvider│
           │ (cloud API)   │                    │  (localhost)    │
           └──────┬───────┘                    └──────┬─────────┘
                  │                                    │
                  ▼                                    ▼
           ┌──────────────┐                    ┌────────────────┐
           │ Google Gemini │                    │  LM Studio /   │
           │ API (remote)  │                    │  Ollama / vLLM │
           └──────────────┘                    └────────────────┘
```

Both providers implement the same `BaseProvider` interface, so swapping is a config change in `settings.yaml`.

---

## Part 1: Manual Setup (You Do This)

### Step 1: Check Your Hardware

Local LLMs need significant resources. Here are the minimum requirements:

| Model Size | VRAM Required | RAM Required | Example GPUs |
|-----------|---------------|-------------|--------------|
| 1B–3B | 2–4 GB | 8 GB | GTX 1060, RTX 3050 |
| 7B–8B (Q4 quantized) | 5–6 GB | 16 GB | RTX 3060, RTX 4060 |
| 7B–8B (FP16) | 14–16 GB | 32 GB | RTX 4090, A4000 |
| 13B (Q4 quantized) | 8–10 GB | 24 GB | RTX 3080 Ti, RTX 4070 Ti |
| 70B (Q4 quantized) | 36–40 GB | 64 GB | 2x RTX 4090, A100 |

> [!IMPORTANT]
> For ARCANE, **7B–8B quantized models** are the sweet spot. They're fast enough for real-time simulation and produce good quality role-play outputs. The simulation calls the LLM 3–8 times per agent per step, so inference speed matters.

**Check your GPU VRAM:**
```bash
# NVIDIA GPUs
nvidia-smi

# AMD GPUs
rocm-smi
```

### Step 2: Install Ollama (Recommended Inference Server)

[Ollama](https://ollama.com) is the recommended local inference server. It's the simplest to set up, provides an OpenAI-compatible API out of the box, handles model management, and supports GPU acceleration automatically.

**Alternatives** (if you prefer):
- **LM Studio** — GUI-based, also exposes an OpenAI-compatible API on `localhost:1234`
- **llama.cpp server** — CLI-only, maximum control, runs on `localhost:8080`
- **vLLM** — Production-grade, best for multi-GPU setups

**Install Ollama:**

| Platform | Command |
|----------|---------|
| **Windows** | Download installer from [ollama.com/download](https://ollama.com/download) |
| **macOS** | `brew install ollama` |
| **Linux** | `curl -fsSL https://ollama.ai/install.sh \| sh` |

**Verify installation:**
```bash
ollama --version
```

### Step 3: Download Models

Pull the models you want to use. ARCANE needs a **chat/instruct** model (not a base model).

#### Recommended Models for ARCANE

| Model | Pull Command | Size | VRAM | Best For |
|-------|-------------|------|------|----------|
| **Llama 3.1 8B** | `ollama pull llama3.1:8b` | 4.7 GB | ~5 GB | Strong role-play, good instruction following |
| **Qwen 2.5 7B** | `ollama pull qwen2.5:7b` | 4.4 GB | ~5 GB | Excellent multilingual, strong reasoning |
| **Mistral 7B v0.3** | `ollama pull mistral:7b` | 4.1 GB | ~5 GB | Fast, good for dialogue |
| **Gemma 2 9B** | `ollama pull gemma2:9b` | 5.4 GB | ~6 GB | Google's open model, solid all-rounder |
| **Phi-3 Mini 3.8B** | `ollama pull phi3:mini` | 2.3 GB | ~3 GB | Smallest viable option for low VRAM |

> [!TIP]
> **Suggested config for ARCANE:**
> - **Benign agents:** `llama3.1:8b` or `qwen2.5:7b` (need natural conversational ability)
> - **Deviant agents:** `qwen2.5:7b` or `mistral:7b` (need persuasion + strategic reasoning)
> - **If low VRAM (< 6 GB):** Use `phi3:mini` for benign agents and `mistral:7b` for deviant agents (swap between them)

**Download your chosen model(s):**
```bash
# Example: pull Llama 3.1 8B and Qwen 2.5 7B
ollama pull llama3.1:8b
ollama pull qwen2.5:7b
```

### Step 4: Start the Ollama Server

```bash
# Start the server (runs on http://localhost:11434 by default)
ollama serve
```

> [!NOTE]
> On Windows, Ollama runs as a background service automatically after installation. You may not need to run `ollama serve` manually.

**Test that it's working:**
```bash
# Quick test — should return a chat response
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.1:8b",
  "messages": [{"role": "user", "content": "Hello, who are you?"}],
  "stream": false
}'
```

### Step 5: (Optional) Configure GPU Layers

Ollama auto-detects your GPU and offloads layers automatically. If you want to control GPU usage:

```bash
# Force CPU-only mode
OLLAMA_NUM_GPU=0 ollama serve

# Limit GPU memory usage
OLLAMA_GPU_MEMORY=4096 ollama serve
```

### Step 6: (Optional) Custom Model Tuning via Modelfile

For better ARCANE persona role-play, you can create a custom Modelfile with tuned parameters:

```dockerfile
# Save as Modelfile.arcane
FROM llama3.1:8b

PARAMETER temperature 0.8
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
PARAMETER repeat_penalty 1.1

SYSTEM "You are a character in a small town social simulation. Stay in character at all times. Respond naturally as the person described in your instructions."
```

```bash
ollama create arcane-llama -f Modelfile.arcane
```

> [!WARNING]
> The `SYSTEM` prompt in the Modelfile is a **default** and will be overridden by the per-agent system prompts ARCANE sends via the API. This is mainly useful for setting the parameter defaults.

---

## Part 2: ARCANE Integration (Done ✅)

The following has been implemented:

### 2.1. `LocalLLMProvider` Class

**File:** `backend/llms/local_provider.py`

This provider:
- Implements `BaseProvider` (same interface as Gemini/OpenRouter)
- Uses the standard OpenAI-compatible API (`POST /v1/chat/completions`)
- Works with LM Studio, Ollama, vLLM, llama.cpp server, or any OpenAI-compatible server
- Supports both sync and async completions via `httpx`
- Handles connection errors gracefully (clear message if server isn't running)
- Support configurable base URL (default `http://localhost:1234/v1` for LM Studio)
- Retry logic for timeouts

**API format (OpenAI-compatible):**
```python
# Standard OpenAI chat completions API
POST http://localhost:1234/v1/chat/completions
{
    "model": "llama3.1:8b",
    "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
    ],
    "stream": false
}
```

**Embedding support:**
- Falls back to hash-based placeholder if no embedding model is configured
- Can use `/v1/embeddings` endpoint if an embedding model is loaded

### 2.2. Provider Registration

**File:** `backend/model.py` (modify)

Add `local` to the provider factory in `get_llm_for_agent()`:

```python
elif provider_name == "local":
    from backend.llms.local_provider import LocalLLMProvider
    local_cfg = self.config.get("local_llm", {})
    self._llm_providers[cache_key] = LocalLLMProvider(
        model=model_name,
        base_url=local_cfg.get("base_url", "http://localhost:1234/v1"),
        timeout=local_cfg.get("timeout", 120),
        embedding_model=local_cfg.get("embedding_model"),
    )
```

### 2.3. Settings Configuration

**File:** `backend/config/settings.yaml` (modify)

Example config for local LLM usage:

```yaml
llm:
  benign_agents:
    provider: local
    model: meta-llama-3.1-8b-instruct
  deviant_agents:
    provider: local
    model: meta-llama-3.1-8b-instruct
  reflection:
    provider: local
    model: meta-llama-3.1-8b-instruct

# Local LLM server configuration
local_llm:
  base_url: http://localhost:1234/v1    # LM Studio default (change for Ollama: http://localhost:11434/v1)
  timeout: 120                           # Seconds — local models can be slow on CPU
  # embedding_model: nomic-embed-text   # Dedicated embedding model (optional)
```

### 2.4. Updated Documentation

- Update `architecture.md` LLM provider table to include Ollama
- Update `README.md` LLM configuration section with Ollama example
- Update `.env.example` to note that no API key is needed for local models

---

## Part 3: Hybrid Configurations

You can mix local and cloud providers. For example:

```yaml
# Budget-friendly: free local for benign, smart cloud for deviant
llm:
  benign_agents:
    provider: local
    model: meta-llama-3.1-8b-instruct    # Free, runs locally
  deviant_agents:
    provider: gemini
    model: gemini-2.5-flash-lite  # Cloud for better strategic reasoning
```

```yaml
# Fully offline
llm:
  benign_agents:
    provider: local
    model: phi-3-mini-4k-instruct     # Smallest model, fast
  deviant_agents:
    provider: local
    model: meta-llama-3.1-8b-instruct # Larger model for complex tactics
```

```yaml
# Using Ollama instead of LM Studio
llm:
  benign_agents:
    provider: local
    model: llama3.1:8b
local_llm:
  base_url: http://localhost:11434/v1    # Ollama's OpenAI-compatible endpoint
```

---

## Checklist Summary

### You Set Up (Manual)
- [ ] Check GPU/VRAM specs
- [ ] Install Ollama (or alternative inference server)
- [ ] Pull at least one chat model (`ollama pull llama3.1:8b`)
- [ ] Start the server (`ollama serve`)
- [ ] Verify it responds (`curl http://localhost:11434/api/chat ...`)
- [ ] (Optional) Pull a second model for agent-type splits
- [ ] (Optional) Pull an embedding model (`ollama pull nomic-embed-text`)
- [ ] (Optional) Create a custom Modelfile for tuned parameters

### I Implement (Automated) ✅
- [x] Create `backend/llms/local_provider.py` implementing `BaseProvider`
- [x] Register `local` in the provider factory (`model.py`)
- [x] Add local_llm config section to `settings.yaml`
- [x] Update docs (architecture.md, README.md)
- [ ] Test connectivity and completion quality

---

## Performance Expectations

| Setup | Speed (per agent step) | Quality |
|-------|----------------------|---------|
| Gemini 2.0 Flash Lite (cloud) | ~1–2s | ★★★★☆ |
| Llama 3.1 8B (RTX 4060) | ~2–4s | ★★★★☆ |
| Qwen 2.5 7B (RTX 3060) | ~3–5s | ★★★★☆ |
| Phi-3 Mini 3.8B (RTX 3050) | ~1–2s | ★★★☆☆ |
| Llama 3.1 8B (CPU only) | ~15–30s | ★★★★☆ (same quality, just slow) |

> [!CAUTION]
> Running on CPU is **very slow** for multi-agent simulations. A 10-step sim with 3 agents makes ~30–80 LLM calls. At 20s per call, that's 10–25 minutes. GPU with ≥6GB VRAM is strongly recommended.

---

## Alternative: Using LM Studio

If you prefer a GUI-based approach:

1. Download [LM Studio](https://lmstudio.ai/)
2. In LM Studio, search and download a model (e.g., "Llama 3.1 8B Instruct GGUF")
3. Go to the **Server** tab → Click **Start Server** (runs on `localhost:1234`)
4. In ARCANE's `settings.yaml`, set:
   ```yaml
   llm:
     benign_agents:
       provider: ollama
       model: llama-3.1-8b-instruct    # model name as shown in LM Studio
   ollama:
     base_url: http://localhost:1234/v1
   ```

LM Studio uses the same OpenAI-compatible API format, so the `OllamaProvider` will work with it unchanged.

---

## Alternative: Using Kimi (Moonshot AI)

Kimi by Moonshot AI is a **cloud API**, not a local model. If you want to use it:

1. Sign up at [platform.moonshot.cn](https://platform.moonshot.cn/)
2. Get an API key
3. Kimi uses an OpenAI-compatible API at `https://api.moonshot.cn/v1`

This would be handled by the existing `OpenRouterProvider` or a minor variant — no local GPU needed, but it's not offline.

---

## Next Steps

Once you've completed the manual setup checklist above, run:
1. Start LM Studio server
2. `python run.py`
3. End-to-end testing with your chosen model
