from dotenv import load_dotenv
from agents.controller import ShoppingAgentController

load_dotenv()
agent = ShoppingAgentController()


def print_divider():
    print("\n" + "=" * 60)


def print_products(ranked):
    print("\n📦 Top Products:\n")

    for i, p in enumerate(ranked[:5], 1):
        print(f"{i}. {p['name']}")
        print(f"   💰 Price   : ₹{p['price']:,.0f}")
        print(f"   ⭐ Rating  : {p['rating'] or 'N/A'}")
        print(f"   🗣 Reviews : {p['reviews'] or 'N/A'}")
        print(f"   🧠 Score   : {p.get('score', 0)}")

        if p.get("source"):
            print(f"   🏬 Source  : {p['source']}")

        if p.get("link"):
            print(f"   🔗 Link    : {p['link']}")

        print("-" * 50)


def run_shopping_agent(query: str):
    print_divider()
    print(f"🔍 Query: {query}")
    print_divider()

    try:
        recommendation, ranked, history = agent.run(query)
    except Exception as e:
        print(f"❌ Error running agent: {e}")
        return

    # 🧠 Agent steps
    print("\n🧠 Agent Thinking:\n")
    for step in history:
        print(f"Step {step['step']} → {step['action']}")
        print(f"  Reason: {step['reason']}")
        print(f"  Result: {step['observation']}\n")

    # ❌ No results
    if not ranked:
        print("😕 No relevant products found.")
        print("👉 Try: 'handbags under 3000' or 'noise earbuds under 2000'")
        return

    # 🏆 Top Recommendation
    top = ranked[0]

    print_divider()
    print("🏆 TOP RECOMMENDATION\n")
    print(top["name"])
    print(f"💰 ₹{top['price']:,.0f} | ⭐ {top['rating'] or 'N/A'} | 🧠 Score: {top.get('score', 0)}")

    if top.get("link"):
        print(f"🔗 {top['link']}")

    # 💡 LLM Recommendation
    print_divider()
    print("💡 AI RECOMMENDATION\n")
    print(recommendation)

    # 📦 Product List
    print_divider()
    print_products(ranked)


if __name__ == "__main__":
    print("🛒 Shopping Agent — AI-Powered Assistant")
    print("=" * 60)

    while True:
        user_input = input("\nWhat are you looking for? (or 'quit'): ").strip()

        if user_input.lower() in ("quit", "exit", "q"):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            print("⚠️ Please enter something.")
            continue

        run_shopping_agent(user_input)