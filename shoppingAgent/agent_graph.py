from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph


# 🧠 STATE (shared memory)
class AgentState(TypedDict, total=False):
    query: str
    keywords: List[str]
    max_price: int
    products: List[Dict]
    ranked: List[Dict]
    recommendation: str
    next: str


# 🔹 1. Intent Node
def intent_node(state: AgentState):
    from agents.intent_agent import parse_intent

    intent = parse_intent(state["query"])

    return {
        "keywords": intent["keywords"],
        "max_price": intent["max_price"]
    }


# 🔹 2. Search Node
def search_node(state: AgentState):
    from agents.search import search

    products = search({
        "keywords": state.get("keywords", []),
        "max_price": state.get("max_price")
    })

    return {"products": products}


# 🔹 3. Decision Node (agent behavior)
def decision_node(state: AgentState):
    if not state.get("products"):
        return {"next": "retry"}
    return {"next": "continue"}


# 🔹 4. Compare Node
def compare_node(state: AgentState):
    from agents.compare import compare

    ranked = compare(state.get("products", []), [])

    return {"ranked": ranked}


# 🔹 5. Recommend Node
def recommend_node(state: AgentState):
    from agents.recommend import recommend

    rec = recommend(state["query"], state.get("ranked", []))

    return {"recommendation": rec}


# 🏗️ BUILD GRAPH
builder = StateGraph(AgentState)

builder.add_node("intent", intent_node)
builder.add_node("search", search_node)
builder.add_node("decision", decision_node)
builder.add_node("compare", compare_node)
builder.add_node("recommend", recommend_node)

builder.set_entry_point("intent")

# 🔁 flow
builder.add_edge("intent", "search")
builder.add_edge("search", "decision")

# 🔥 conditional routing (agent logic)
builder.add_conditional_edges(
    "decision",
    lambda state: state["next"],
    {
        "retry": "search",      # retry search if no products
        "continue": "compare"
    }
)

builder.add_edge("compare", "recommend")

graph = builder.compile()


# 🚀 MAIN FUNCTION
def run_agent(query: str):
    return graph.invoke({"query": query})