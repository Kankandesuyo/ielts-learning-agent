from typing import Any


def make_graph_runner(step):
    """Return a LangGraph runner when installed, otherwise a simple callable.

    This keeps the MVP runnable for beginners even before they understand every
    LangGraph concept. In production, add more nodes: retrieve -> reason -> save.
    """

    try:
        from langgraph.graph import END, StateGraph
        from typing_extensions import TypedDict

        class AgentState(TypedDict, total=False):
            input: dict[str, Any]
            output: dict[str, Any]

        graph = StateGraph(AgentState)

        def node(state: AgentState) -> AgentState:
            return {"input": state["input"], "output": step(state["input"])}

        graph.add_node("agent_step", node)
        graph.set_entry_point("agent_step")
        graph.add_edge("agent_step", END)
        app = graph.compile()

        def run(payload: dict[str, Any]) -> dict[str, Any]:
            result = app.invoke({"input": payload})
            return result["output"]

        return run
    except Exception:
        return step


def split_minutes(total: int, weak_skills: list[str]) -> dict[str, int]:
    base = {"listening": 20, "reading": 20, "writing": 25, "speaking": 20, "vocabulary": 15}
    for skill in weak_skills:
        key = skill.lower()
        if key in base:
            base[key] += 10
    weight_sum = sum(base.values())
    return {key: max(5, round(total * weight / weight_sum)) for key, weight in base.items()}

