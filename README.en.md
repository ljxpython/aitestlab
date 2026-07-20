<h1 align="center">Enterprise AI Agent Platform</h1>

<p align="center"><strong>An AI agent platform foundation for enterprise delivery and secondary development</strong></p>

<p align="center">English | <a href="README.md">中文</a></p>

<p align="center">
  <img src="https://img.shields.io/badge/Vue-3%20Workspace-42B883" alt="Vue 3 Workspace" />
  <img src="https://img.shields.io/badge/Testcase-Agent%20Live-2563EB" alt="Testcase Agent Live" />
  <img src="https://img.shields.io/badge/Skills-Private%20Skill%20Stack-0F766E" alt="Skills" />
  <img src="https://img.shields.io/badge/MCP-Knowledge%20Ready-7C3AED" alt="MCP Knowledge Ready" />
  <img src="https://img.shields.io/badge/Harness-AI%20Continuous%20Coding-F59E0B" alt="Harness" />
  <img src="https://img.shields.io/badge/LangGraph-Runtime%20Core-111827" alt="LangGraph Runtime Core" />
  <a href="https://github.com/ljxpython/ai-agent-platform/releases/latest"><img src="https://img.shields.io/github/v/release/ljxpython/ai-agent-platform" alt="Latest Release" /></a>
  <img src="https://img.shields.io/badge/README-EN%2FZH-F59E0B" alt="README EN/ZH" />
</p>

<p align="center"><a href="#system-overview">System Overview</a> · <a href="#frontend-entry">Frontend Entry</a> · <a href="#quick-start">Quick Start</a> · <a href="docs/deployment-guide.md">Deployment Guide</a> · <a href="https://github.com/ljxpython/ai-agent-platform/releases/tag/v0.3.1">Latest Release</a> · <a href="docs/CHANGELOG.md">Changelog</a> · <a href="#acknowledgements">Acknowledgements</a> · <a href="#ai-deploy">AI Deployment</a></p>

## Testcase Agent Demo

<p align="center">
  <a href="https://youtu.be/SVplU-uIci0">
    <img src="docs/assets/testcase-agent-demo-preview.jpg" alt="Testcase Agent Demo" width="100%" />
  </a>
</p>

<p align="center">
  <strong><a href="https://youtu.be/SVplU-uIci0">▶ Watch the current platform Testcase Agent demo</a></strong>
</p>

<p align="center"><sub>The GitHub README uses an image preview here. Click it to open the YouTube demo.</sub></p>

An enterprise AI agent platform architecture built on `LangGraph / LangChain`, intended as a reusable foundation for further development.  
It separates the **platform governance layer** from the **Agent Runtime execution layer**, so the repo can support platform-side authentication, project management, audit, and catalog management, while also supporting runtime graph orchestration, model assembly, Tools / MCP / Skills integration, and rapid agent debugging.

The repository currently provides a default five-service local bring-up path, plus an optional runtime debug entry. It is suitable for:

- Teams that want to build on mainstream agent infrastructure instead of inventing a closed framework
- Projects that need both platform capabilities and agent execution capabilities
- Developers who want to validate LangGraph Runtime behavior and frontend interaction quickly
- Teams that want to bring AI-assisted collaboration into the real engineering workflow

> If you want to understand why the project is designed this way and how development should continue, start with [docs/development-paradigm.md](docs/development-paradigm.md). Most supporting docs in this repo are currently Chinese-first.

<a id="frontend-entry"></a>

## Current Frontend Entry

`apps/platform-web` is the official platform frontend host and the default place for current platform frontend development.

Use the frontend entries in this repo like this:

- `apps/platform-web`: official platform workspace frontend
- `apps/runtime-web`: runtime-facing debug frontend

If you just want the current official local demo path, start the root scripts and open `apps/platform-web`.

## AI Continuous-Coding Harness

This repository is not only a codebase. It already acts as an engineering harness for continuous AI-assisted development.

That harness is made of several parts working together:

- `Boundaries`: platform governance, runtime execution, debug frontend, and result-domain service are separated instead of mixed together
- `Contracts`: local deployment contract, env conventions, startup order, API naming, and demo account rules are fixed
- `Patterns`: `runtime-service`, `platform-web`, control-plane standards, and reusable examples already provide working implementation patterns
- `Delivery loop`: helper scripts, health checks, smoke tests, acceptance docs, changelog, and release runbooks form a repeatable delivery path

In short, the repo is meant to let AI agents keep building inside a controlled engineering environment, not just generate random code in a vacuum.

The current entry docs for that harness are:

1. `AGENTS.md`
2. `docs/standards/01-ai-execution-system.md`
3. `docs/ai-execution-system-usage-guide.md`
4. `docs/README.md`

Use the explicit project router in Codex when a task needs a B1/B2/B3 decision:

```text
$route-project-change <task description>
```

The router does not override root rules, leaf standards, human approval, or verification
gates. Machines that execute persisted B2/B3 workflows also need the OpenSpec CLI. See
[the AI execution usage guide](docs/ai-execution-system-usage-guide.md#5-openspec-怎么参与)
for installation, the six official Skills, and the full lifecycle.

## What Problem This Project Solves

Many agent projects can run a demo, but once they enter a real engineering context, things become messy fast: platform governance, runtime execution, debug entrypoints, and environment configuration all get coupled together.

This repo has a clear goal:

- Build an enterprise AI platform architecture on top of the mainstream `LangGraph / LangChain` ecosystem
- Decouple the platform layer from the runtime layer so ownership, evolution, and delivery stay manageable
- Provide a reusable runtime execution skeleton instead of a one-off demo
- Leave room for later business customization and testing-related scenarios

## Frontend Showcase

If you want to see what the current platform frontend already looks like and how the frontend workspace is organized, start with this write-up:

- [Platform frontend showcase and introduction](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260325_platform_frontend_intro.md)

That article is more frontend-oriented and is useful for quickly understanding the current platform workspace structure and UI direction.

![Platform Frontend Showcase](docs/assets/image-20260325161139758.png)

<a id="system-overview"></a>

## System Overview

The default local bring-up currently includes five formal services:

- `apps/interaction-data-service`: result-domain data service for workflow result persistence and querying
- `apps/platform-api`: official platform backend / control-plane API
- `apps/platform-web`: official platform frontend / admin workspace entry
- `apps/runtime-service`: LangGraph execution layer / Agent Runtime
- `apps/lightrag-service`: in-repo knowledge service that provides both the `platform-api` LightRAG HTTP lane and the `runtime-service` project-scoped MCP lane

Optional in-repo services:

- `apps/runtime-web`: debug frontend that talks directly to the runtime

### Main Paths

- Platform path: `platform-web -> platform-api -> runtime-service`
- Debug path: `runtime-web -> runtime-service`
- Result-domain path: `runtime-service -> interaction-data-service`
- Knowledge HTTP path: `platform-api -> lightrag-service`
- Knowledge MCP path: `runtime-service -> lightrag-service`

### What The Frontend Entries Are For

- `platform-web`: official platform product workspace and the default frontend host
- `runtime-web`: agent debugging, interaction validation, and fast runtime iteration

## Architecture Diagram

![System Architecture Diagram](docs/assets/system-architecture.en.svg)

<a id="quick-start"></a>

## Quick Start

### Default Startup Order

1. `runtime-service`
2. `interaction-data-service`
3. `lightrag-service`
4. `platform-api`
5. `platform-web`
6. `runtime-web` (optional)

### Root Scripts

```bash
scripts/dev-up.sh
scripts/check-health.sh
scripts/dev-down.sh
```

These three scripts are:

- Start: `scripts/dev-up.sh`
- Health check: `scripts/check-health.sh`
- Stop: `scripts/dev-down.sh`

### If You Want To Start `platform-web` Separately

The root scripts already start `apps/platform-web`.

If you want to run it alone during frontend work:

```bash
VITE_DEV_PORT=3002 pnpm --dir "apps/platform-web" dev
```

Then open:

- `platform-web`: `http://127.0.0.1:3002`

### Default Local Ports

- `interaction-data-service`: `8081`
- `runtime-service`: `8123`
- `lightrag-service` HTTP: `9621`
- `lightrag-service` MCP SSE: `8621`
- `platform-api`: `2142`
- `platform-web`: `3000`
- `runtime-web`: `3001`

### URLs After Startup

- `platform-web`: `http://127.0.0.1:3000`
- `runtime-web`: `http://127.0.0.1:3001`

### Minimum Health Checks

```bash
curl http://127.0.0.1:8081/_service/health
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:9621/health
curl http://127.0.0.1:8621/sse
curl http://127.0.0.1:2142/_system/health
curl http://127.0.0.1:2142/api/langgraph/info
```

If `/api/langgraph/info` on `platform-api`, `/_service/health` on
`interaction-data-service`, and `/health` on `lightrag-service` all succeed, the platform,
result persistence, and knowledge HTTP paths are basically connected. The unified health
script also checks MCP SSE connectivity.

![Local Startup Flow](docs/assets/local-dev-startup-flow.en.svg)

## Repo Structure

```text
AITestLab/
├── apps/
│   ├── interaction-data-service/
│   ├── lightrag-service/
│   ├── platform-api/
│   ├── platform-web/
│   ├── runtime-service/
│   ├── runtime-web/
│   └── ...
├── .codex/skills/
├── .harness/
├── docs/
├── openspec/
├── scripts/
└── archive/
```

- `apps/`: business apps, including the default local startup set and other maintained application directories
- `.codex/skills/`: portable project-level Codex and OpenSpec Skills
- `.harness/`: helpers, historical plans, and repo-level verification reports
- `docs/`: deployment, development, constraints, and background docs
- `openspec/`: persisted B2/B3 changes, approved capability specs, and archives
- `scripts/`: unified start, stop, and health-check scripts
- `archive/`: historical archive notes

<a id="docs-by-goal"></a>

## Read Docs By Goal

![Documentation Navigation Diagram](docs/assets/readme-doc-navigation.en.svg)

### I Want To Bring Up The Environment First

Start with:

- `docs/local-deployment-contract.yaml`
- `docs/local-dev.md`
- `docs/env-matrix.md`

### I Want Full Deployment Details

Then read:

- `docs/deployment-guide.md`

### I Want To Continue Development Or Customize The Project

Focus on:

- `docs/standards/01-ai-execution-system.md`
- `docs/ai-execution-system-usage-guide.md`
- `docs/development-guidelines.md`
- `docs/project-story.md`

### I Want To Do An Official Release

Start with:

- `docs/releases/release-policy.md`
- `docs/releases/v0.3.1-agent-workspace-demo-draft.md`
- `docs/releases/v0.3.1-release-runbook.md`
- `docs/releases/` for the complete release history

<a id="ai-deploy"></a>

### I Want An AI Agent To Help Me Deploy

Entry document:

- `docs/ai-deployment-assistant-instruction.md`

If you only want to trigger the standard local deployment flow, this sentence is enough:

```text
Read `docs/ai-deployment-assistant-instruction.md` and help me deploy the environment.
```

If you already know which models should be used locally, it is better to provide the model configuration to the agent in the same message. That makes it much easier for the agent to finish the bring-up in one pass instead of stopping midway to ask for runtime model settings.

This fuller prompt is the recommended version. Replace the placeholders with your real values, and only let the agent write them into local `settings.local.yaml`. Do not commit real secrets back into the repo.

```text
Read `docs/ai-deployment-assistant-instruction.md` and help me deploy the environment.

Use `<YOUR_REASONING_MODEL_ID>` as the default reasoning model.
Also configure `<YOUR_MULTIMODAL_MODEL_ID>` for the current multimodal pipeline.
If runtime model config is missing locally, write the following into `apps/runtime-service/runtime_service/conf/settings.local.yaml`, then continue deployment, startup, and verification. Do not commit the real API key back to the repo.

default:
  default_model_id: <YOUR_REASONING_MODEL_ID>
  models:
    <YOUR_MULTIMODAL_MODEL_ID>:
      alias: <OPTIONAL_MULTIMODAL_ALIAS>
      model_provider: openai
      model: <YOUR_MULTIMODAL_MODEL_NAME>
      base_url: <YOUR_PROVIDER_BASE_URL>
      api_key: <YOUR_API_KEY>
    <YOUR_REASONING_MODEL_ID>:
      alias: <OPTIONAL_REASONING_ALIAS>
      model_provider: openai
      model: <YOUR_REASONING_MODEL_NAME>
      base_url: <YOUR_PROVIDER_BASE_URL>
      api_key: <YOUR_API_KEY>
```

## Practical References

If you want a set of notes closer to real development work, see:

- [ai-learning-portfolio repository](https://github.com/ljxpython/ai-learning-portfolio)
- [my_work_record index](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/README.md)

These notes do not duplicate the source code. They focus on the practical path: how things were done, how they were verified, and how they were reviewed afterward. They are useful as a reference for both **agent capability development** and **platform capability development** in this repo.

A useful way to think about them:

- The root `README` of this repo is more of a project map, system layering guide, and document index
- The `ai-learning-portfolio` notes are more about real implementation flow, validation steps, and retrospective thinking

If you want the mainline reading path, start with:

- [Deployment and validation baseline](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260323_deployment_environment.md)
- [A simple Text-to-SQL capability case](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260312_texttosql_rd.md)
- [A complex multi-agent business case](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260314_requirement_agent_rd.md)

You can read those three notes like this:

- `20260323_deployment_environment.md`: how to prepare the local environment, start services, and verify that paths are connected
- `20260312_texttosql_rd.md`: how a relatively simple Text-to-SQL capability is designed and implemented around a concrete scenario
- `20260314_requirement_agent_rd.md`: how a more complex multi-agent business scenario moves from requirement understanding and role split to actual delivery

If this is your first time looking at the repo, the recommended reading order is:

1. Read this `README`, `docs/local-deployment-contract.yaml`, and `docs/local-dev.md`
2. Then check the local practice index in `ai-learning-portfolio`
3. If you want a simpler starting point, begin with Text-to-SQL. If you want a more complex collaboration case, start with the multi-agent requirement case

## Current Status

This repo has already completed:

- The default local startup set under `apps/*` now includes the repo-local LightRAG service lanes
- `apps/platform-web` is the official platform frontend host
- `apps/platform-api` is the official platform control plane
- `runtime-service` can start
- `interaction-data-service` can start
- `platform-api` can start
- `platform-api -> runtime-service` integration has passed
- `runtime-service -> interaction-data-service` has been wired into the local bring-up scripts
- `lightrag-service` HTTP + MCP are now wired into the default local one-click startup scripts
- `platform-web` is the official platform frontend host, while `runtime-web` remains the optional runtime debug shell
- `apps/lightrag-service` is now part of the default local one-click bring-up, while the Compose stack still keeps it as an explicit opt-in lane
- Harness and OpenSpec now cover routing, the B3 pre-apply gate, durable verification evidence, spec sync, archive, and CI enforcement
- The current release is [`v0.3.1`](https://github.com/ljxpython/ai-agent-platform/releases/tag/v0.3.1)

Current conventions that are still kept:

- Each app maintains its own environment and dependencies
- There is no unified root `.env`
- Python and Node dependencies are not unified at the repo root for now

## Project Direction

The long-term direction of this repo is to evolve into a reusable, extensible, secondary-development-friendly AI agent platform foundation.  
Near-term capability growth is biased toward test-engineering-related scenarios such as:

- AI-assisted review
- AI-driven UI automation
- Automated script generation and testing assistance
- AI performance testing
- Text-to-SQL

For fuller project background, evolution history, and design tradeoffs, see:

- `docs/project-story.md`

## Support And Contact

If this repo helps you, a star is welcome.  
If you want to discuss testing platforms, AI-assisted development, or LangGraph / MCP practice, feel free to reach out.

Personal WeChat:

<img src="docs/assets/image-20250531212549739.png" alt="Personal WeChat QR" width="300"/>

## Historical Code

The old `AITestLab` code is no longer kept on the current working branch.

If you need the historical code, see:

- [AITestLab-archive](https://github.com/ljxpython/AITestLab-archive)

<a id="acknowledgements"></a>

## Acknowledgements

This project has benefited from several strong open-source projects and ecosystems, especially:

- [Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api/tree/main): strong inspiration for frontend layout rhythm, dashboard organization, and workspace interaction patterns
- [FastAPI](https://fastapi.tiangolo.com/): key foundation for the platform backend and service interfaces
- [LangGraph](https://docs.langchain.com/langgraph): key foundation for agent runtime orchestration and stateful execution flows
- [FastMCP](https://gofastmcp.com/): important reference ecosystem for MCP-based tooling and service integration
- [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG): important reference for project-scoped knowledge retrieval and the optional in-repo LightRAG MCP integration path

These references are not copied blindly. They are absorbed, reorganized, and adapted around the goals and engineering boundaries of this repository.

## Open Source Usage Notice

This project is maintained as public source code. Learning from it, referencing it, and building on top of it are all welcome.

If you use this project in public repositories, technical articles, demos, training materials, or redistributed derivatives, please clearly credit the original repository and author.
