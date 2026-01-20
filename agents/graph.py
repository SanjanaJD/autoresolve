"""AutoResolve - LangGraph Workflow Definition"""
from langgraph.graph import StateGraph, END
from agents.state import AutoResolveState, Issue, ResolutionStatus, Severity
from agents.agents import triage_agent, diagnostic_agent, fix_agent, escalation_agent
from datetime import datetime


def create_initial_state(issue: Issue) -> AutoResolveState:
    """Create initial state from an issue"""
    return {
        "issue": issue,
        "triage_result": None,
        "diagnostic_result": None,
        "fix_attempts": [],
        "current_attempt": 0,
        "max_attempts": 3,
        "status": ResolutionStatus.DETECTED,
        "resolution_summary": None,
        "next_agent": "triage",
        "messages": []
    }


def route_after_triage(state: AutoResolveState) -> str:
    """Route after triage based on severity"""
    triage = state.get("triage_result")
    if triage and triage.severity == Severity.CRITICAL:
        # Critical: still diagnose but with urgency
        return "diagnostic"
    return "diagnostic"


def route_after_diagnostic(state: AutoResolveState) -> str:
    """Route after diagnostic based on fixability"""
    diagnostic = state.get("diagnostic_result")
    if diagnostic and diagnostic.is_auto_fixable:
        return "fix"
    return "escalate"


def route_after_fix(state: AutoResolveState) -> str:
    """Route after fix attempt"""
    if state["status"] == ResolutionStatus.RESOLVED:
        return "complete"
    if state["current_attempt"] >= state["max_attempts"]:
        return "escalate"
    return "diagnostic"  # Retry


def build_graph() -> StateGraph:
    """Build the LangGraph workflow"""
    
    # Create graph
    graph = StateGraph(AutoResolveState)
    
    # Add nodes
    graph.add_node("triage", triage_agent)
    graph.add_node("diagnostic", diagnostic_agent)
    graph.add_node("fix", fix_agent)
    graph.add_node("escalate", escalation_agent)
    graph.add_node("complete", lambda state: state)  # Terminal node
    
    # Set entry point
    graph.set_entry_point("triage")
    
    # Add edges
    graph.add_conditional_edges("triage", route_after_triage)
    graph.add_conditional_edges("diagnostic", route_after_diagnostic)
    graph.add_conditional_edges("fix", route_after_fix)
    graph.add_edge("escalate", "complete")
    graph.add_edge("complete", END)
    
    return graph.compile()


# Create the compiled graph
workflow = build_graph()


async def run_autoresolve_workflow(issue_data: dict) -> dict:
    """Run the complete AutoResolve workflow"""
    from agents.state import Issue, Severity
    
    # Convert alert data to Issue
    issue = Issue(
        id=issue_data.get("id", f"issue-{datetime.utcnow().timestamp()}"),
        title=issue_data.get("title", issue_data.get("labels", {}).get("alertname", "Unknown")),
        description=issue_data.get("description", ""),
        severity=Severity(issue_data.get("severity", "warning")),
        service_name=issue_data.get("service_name", "demo-app"),
        namespace=issue_data.get("namespace", "default"),
        labels=issue_data.get("labels", {}),
        annotations=issue_data.get("annotations", {}),
        started_at=issue_data.get("started_at", datetime.utcnow().isoformat()),
        raw_data=issue_data
    )
    
    # Create initial state
    initial_state = create_initial_state(issue)
    
    # Run the workflow
    print(f"\n🚀 Starting AutoResolve workflow for: {issue.title}")
    print("=" * 60)
    
    final_state = await workflow.ainvoke(initial_state)
    
    print("=" * 60)
    print(f"✅ Workflow complete. Status: {final_state['status'].value}")
    print(f"📝 Summary: {final_state.get('resolution_summary', 'N/A')}")
    
    return final_state
