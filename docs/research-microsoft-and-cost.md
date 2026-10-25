# Research: Microsoft tech, cost, and existing simulators

> Written Oct 24, 2026 from public web sources. Prices and free-tier terms change: confirm in the Azure pricing calculator and your own portal before relying on them.

## 1. LLM cost

**Model prices (per 1M tokens, input / output)**

| Model | Price | Note |
| --- | --- | --- |
| GPT-4.1 nano | $0.10 / $0.40 | Same on Azure and OpenAI per cost-calculator sites; cached input $0.02. Fastest and cheapest of the GPT-4.1 series; suited to classification and short text |
| GPT-4.1 mini | $0.40 / $1.60 | Cheapest at Azure OpenAI per cloudprice.net |

**Estimate for pre-generating all hero-match commentary**

- Assumption: 22 players x Casual/Analyst x EN/ES = 88 combinations, about 300 moments each, so about 26,000 short lines.
- Rough cost: **about $2 on nano, about $8 on mini.** This depends on prompt length and the assumed moment count; measure on a small batch first.
- Both are well inside the $200 Azure free credit (30 days). Sign up early so the credit window covers judging through Nov 10.
- Set a $5 budget alert anyway.

**Cost rules that follow**

- Pre-generate once, then serve cache only. Visitors cost $0.
- No live LLM calls for anonymous visitors. Keys in env vars only; anyone cloning the public repo brings their own.
- Claude models in Foundry need pay-as-you-go, so use an OpenAI model on the free account.

## 2. Microsoft technologies

**Microsoft Foundry.** The portal where a model deployment is created and an endpoint plus key are issued. Call it with the OpenAI SDK. Smoke test: deploy one small model and call it from a 10-line Python script.

**Microsoft Agent Framework**

- Open-source (MIT) SDK for building agents and multi-agent workflows, in Python and .NET.
- Direct successor to Semantic Kernel and AutoGen, built by the same teams. One source reports version 1.0 shipped April 3, 2026 with stable APIs.
- Two capabilities: **Agents** (LLM-backed, can call tools and MCP servers; providers include Microsoft Foundry, Anthropic, Azure OpenAI, OpenAI, Ollama) and **Workflows** (graph-based pipelines connecting agents and functions, with type-safe routing, checkpointing and human-in-the-loop).
- Why it matters: the Multi-Agent prize text names Agent Framework explicitly, and judges look for distinct roles, shared state, effective handoffs and recovery from failure. Run the pipeline on it, not on hand-rolled async code.
- Check the official docs for the current Python install command before using it.

**Azure Container Apps**

- Serverless containers (Docker). Consumption plan free grant per subscription per month: 180,000 vCPU-seconds, 360,000 GiB-seconds, 2 million requests.
- With min replicas 0 the app scales to zero and you pay only when active; set min replicas to 1 during judging to avoid cold starts (a few dollars of credit).
- **Apple Silicon note:** build images with `--platform linux/amd64`, or the container won't run on Azure.

**GitHub Copilot agent mode**

- Copilot's multi-step agent inside the IDE. Separate from Claude Code, but Copilot can use Claude models on supported plans.
- Copilot Free reportedly includes about 50 premium requests per month (secondary source). Use it for a few real tasks (tests, README) so the README can honestly claim it.

**Azure MCP Server**

- Open-source, free. Lets AI agents and clients (e.g. Copilot agent mode) interact with Azure resources through natural-language commands over MCP, using Entra ID for auth.
- Optional: use it once to inspect or deploy resources and mention it in the README.

## 3. Stage-one viability

Stage one of judging is pass/fail on whether the project reasonably fits the theme and applies the hero technologies. Minimum to show: Foundry (model), Agent Framework (agents), Azure Container Apps (hosting), Copilot agent mode (some real dev work). Azure MCP is a bonus.

## 4. Existing simulators surveyed (why we write our own)

| Project | What it is | Verdict |
| --- | --- | --- |
| Google Research Football | Open-source (Apache 2.0) 11v11 physics engine built for reinforcement learning; a 2025 paper used it to collect simulated tracking data in a real-tracking-like schema | Too heavy to install and tune in 3.5 days |
| SoccER (Politecnico di Torino) | Modified Gameplay Football engine (C++/Python) that outputs player positions plus auto-labeled events; 500 minutes, over 1M events in its dataset | Same: heavy, and output isn't shaped for our contracts |
| Football-Simulator (GitHub, AllenThomasDev) | Python league sim, minute-by-minute event probabilities scaled by team strength, FIFA 20 stats | Scoreline-level only, no positions; and uses real data |
| PressIQ (GitHub) | React + FastAPI analytics platform with a synthetic possession simulator, StatsBomb open data, optional LLM | Useful reference for structure; not a drop-in |

**Decision:** write a lightweight seeded Python simulator (numpy) that records positions every second and emits unique-ID events. It's also stronger for the "creativity and optimized synthetic data creation" judging criterion.

## 5. Sources

- [GPT-4.1 nano on Azure (cost calculator)](https://www.getmaxim.ai/bifrost/llm-cost-calculator/provider/azure/model/gpt-4.1-nano-2025-04-14.md)
- [GPT-4.1 mini pricing](https://cloudprice.net/models/gpt-4.1-mini)
- [Azure Container Apps pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/)
- [Microsoft Agent Framework overview](https://learn.microsoft.com/agent-framework/overview/agent-framework-overview)
- [Agent Framework summary (atlan.com)](https://atlan.com/know/ai-agent/microsoft/agent-framework/)
- [Azure MCP Server overview](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/overview)
- [GitHub Copilot supported models](https://docs.github.com/copilot/using-github-copilot/ai-models/using-claude-in-github-copilot)
- [Simulating Tracking Data to Advance Sports Analytics Research](https://arxiv.org/pdf/2503.19809)
- [SoccER data generator](https://iris.polito.it/handle/11583/2847886)
- [Football-Simulator](https://www.github.com/AllenThomasDev/Football-Simulator)
- [PressIQ](https://github.com/AtaSakik/PressIQ)
