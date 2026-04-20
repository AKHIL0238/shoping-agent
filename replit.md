# ShopMind AI - Shopping Agent

## Overview
A multi-agent AI shopping assistant that helps users find and compare products across Indian e-commerce platforms. Uses a ReAct architecture powered by Claude (Anthropic) and SerpAPI (Google Shopping).

## Tech Stack
- **Frontend:** Streamlit (glassmorphism dark theme UI)
- **LLM:** Claude via Anthropic API
- **Search:** SerpAPI (Google Shopping India)
- **Agent Framework:** LangGraph
- **Language:** Python 3.11

## Project Structure
```
shoppingAgent/
  app.py              - Streamlit web application (entry point)
  main.py             - CLI application
  requirements.txt    - Python dependencies
  agents/
    react_agent.py    - Core ReAct agent using Claude
    controller.py     - Orchestration wrapper
    memory.py         - Persistent memory (search history, preferences)
    tools_registry.py - Tool schemas and execution
    search.py         - SerpAPI search interface
  tools/
    product_api.py    - Product search API
  utils/
    price_monitor.py  - Price drop monitoring
    cart.py           - Virtual shopping cart
    ui_components.py  - CSS/HTML templates for Streamlit
  agent_graph.py      - LangGraph state machine
```

## Running the App
```
cd shoppingAgent && streamlit run app.py --server.port 5000 --server.address 0.0.0.0 --server.headless true
```

## Required Environment Variables
- `ANTHROPIC_API_KEY` - Claude API key
- `SERPAPI_API_KEY` - SerpAPI key for Google Shopping

## GitHub Push Note
The GitHub OAuth integration was dismissed by the user. To push to GitHub manually, a Personal Access Token (PAT) with `repo` scope is needed. Store it as a secret `GITHUB_TOKEN` and use git with the token in the remote URL:
```
git remote set-url origin https://<token>@github.com/<user>/<repo>.git
git push origin main
```
