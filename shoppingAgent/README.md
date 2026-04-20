# 🛒 Shopping Agent — AI-Powered Personal Shopping Assistant

## Problem Statement

Online shopping platforms like Amazon and Flipkart offer millions of products, but availability is no longer the challenge — **decision-making is**.

Users struggle with:

- **Too many options** → decision fatigue and confusion
- **Time-consuming comparisons** → manually checking multiple products and pages
- **Fake reviews / biased ratings** → hard to trust what you read
- **Poor value-for-money discovery** → best deals are buried
- **No personalization** → generic results that don't match individual needs

> "How can we build an intelligent system that acts like a personal shopping assistant — one that understands user needs, searches products, compares them, and suggests the best option automatically?"

---

## Solution Overview

A multi-agent AI system that:

1. **Understands** user intent through natural language input
2. **Searches** products across platforms using APIs or web tools
3. **Compares** options based on price, ratings, reviews, and value
4. **Recommends** the best match tailored to the user's needs

---

## Goals

- Reduce decision fatigue for online shoppers
- Provide trustworthy, unbiased product comparisons
- Deliver personalized recommendations automatically
- Save users time and money

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Llama 3.1 8B Instant (`llama-3.1-8b-instant`) via Groq API |
| Product Search | SerpAPI — Google Shopping (India) |
| Web UI | Streamlit |
| Environment | python-dotenv |

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
SERPAPI_API_KEY=your_serpapi_key_here
```

---

## Running the App

**Web UI (Streamlit)**
```bash
streamlit run app.py
```
Opens at `http://localhost:8501`

**CLI**
```bash
python main.py
```

---

## Agent Architecture

This project now uses an autonomous agent controller that decides which tool to run next based on the user's goal.

```
User Query → Agent Controller → [ Intent Agent, Search Agent, Compare Agent, Recommend Agent ]
```

| Component | File | Description |
|-----------|------|-------------|
| Controller | `agents/controller.py` | Chooses actions, tracks state, and orchestrates the agent workflow |
| Intent | `agents/intent_agent.py` | Parses natural language query into structured shopping intent |
| Search | `agents/search_agent.py` | Fetches real products from Google Shopping via SerpAPI |
| Compare | `agents/compare_agent.py` | Scores and ranks products by rating, reviews, and price value |
| Recommend | `agents/recommend_agent.py` | Generates a natural language recommendation using Claude Haiku |
