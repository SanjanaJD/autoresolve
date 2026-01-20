"""AutoResolve - Agent Definitions"""
import os
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal

from agents.state import (
    AutoResolveState, TriageResult, DiagnosticResult, FixAttempt,
    IssueType, Severity, ResolutionStatus
)
from agents.k8s_tools import K8S_TOOLS

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0
)


# ============== TRIAGE AGENT ==============

class TriageOutput(BaseModel):
    issue_type: IssueType
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    recommended_action: str

TRIAGE_PROMPT = """You are an SRE AI agent responsible for triaging production alerts.

Classify this alert and determine severity:

SEVERITY LEVELS:
- critical: System down, immediate action needed
- warning: Degraded performance, needs attention
- info: Informational, monitor only

ISSUE TYPES:
- high_cpu: CPU usage above threshold
- high_memory: Memory usage above threshold  
- high_error_rate: Error rate above threshold
- pod_crash: Pod crash looping
- unknown: Cannot classify

ALERT DATA:
{alert_data}

Provide your classification."""

async def triage_agent(state: AutoResolveState) -> dict:
    """Classify the issue and determine severity"""
    issue = state["issue"]
    
    structured_llm = llm.with_structured_output(TriageOutput)
    
    response = await structured_llm.ainvoke([
        HumanMessage(content=TRIAGE_PROMPT.format(
            alert_data=issue.model_dump_json(indent=2)
        ))
    ])
    
    triage_result = TriageResult(
        issue_type=response.issue_type,
        severity=response.severity,
        confidence=response.confidence,
        reasoning=response.reasoning,
        recommended_action=response.recommended_action
    )
    
    return {
        "triage_result": triage_result,
        "status": ResolutionStatus.DIAGNOSING,
        "next_agent": "diagnostic",
        "messages": [{
            "role": "triage",
            "content": f"Classified as {response.issue_type.value} ({response.severity.value}): {response.reasoning}"
        }]
    }


# ============== DIAGNOSTIC AGENT ==============

class DiagnosticOutput(BaseModel):
    root_cause: str
    affected_pods: list[str]
    is_auto_fixable: bool
    fix_action: Literal["restart", "rollback", "scale", "escalate"]
    confidence: float = Field(ge=0, le=1)

DIAGNOSTIC_PROMPT = """You are an SRE AI agent performing root cause analysis.

Based on the triage result and Kubernetes data, determine:
1. The root cause of the issue
2. Which pods are affected
3. Whether this can be auto-fixed
4. What fix action to take

TRIAGE RESULT:
{triage_result}

KUBERNETES DATA:
Pod Status: {pod_status}
Events: {events}

Determine the root cause and recommended fix."""

async def diagnostic_agent(state: AutoResolveState) -> dict:
    """Perform root cause analysis using K8s tools"""
    from agents.k8s_tools import get_pod_status, get_kubernetes_events
    
    # Gather diagnostic data
    pod_status = get_pod_status.invoke({"namespace": "default", "label_selector": "app=demo-app"})
    events = get_kubernetes_events.invoke({"namespace": "default"})
    
    structured_llm = llm.with_structured_output(DiagnosticOutput)
    
    response = await structured_llm.ainvoke([
        HumanMessage(content=DIAGNOSTIC_PROMPT.format(
            triage_result=state["triage_result"].model_dump_json(indent=2),
            pod_status=pod_status,
            events=events
        ))
    ])
    
    diagnostic_result = DiagnosticResult(
        root_cause=response.root_cause,
        affected_pods=response.affected_pods,
        is_auto_fixable=response.is_auto_fixable,
        fix_action=response.fix_action,
        confidence=response.confidence
    )
    
    next_agent = "fix" if response.is_auto_fixable else "escalate"
    
    return {
        "diagnostic_result": diagnostic_result,
        "status": ResolutionStatus.FIXING if response.is_auto_fixable else ResolutionStatus.ESCALATED,
        "next_agent": next_agent,
        "messages": [{
            "role": "diagnostic",
            "content": f"Root cause: {response.root_cause}. Action: {response.fix_action}"
        }]
    }


# ============== FIX AGENT ==============

async def fix_agent(state: AutoResolveState) -> dict:
    """Execute the fix based on diagnostic results"""
    from datetime import datetime
    from agents.k8s_tools import restart_deployment, rollback_deployment, scale_deployment
    
    diagnostic = state["diagnostic_result"]
    current_attempt = state["current_attempt"] + 1
    
    # Execute the appropriate fix
    fix_actions = {
        "restart": lambda: restart_deployment.invoke({"deployment_name": "demo-app"}),
        "rollback": lambda: rollback_deployment.invoke({"deployment_name": "demo-app"}),
        "scale": lambda: scale_deployment.invoke({"deployment_name": "demo-app", "replicas": 3}),
    }
    
    action = diagnostic.fix_action
    if action in fix_actions:
        result = fix_actions[action]()
        success = "✅" in result
    else:
        result = "Unknown action"
        success = False
    
    fix_attempt = FixAttempt(
        attempt_number=current_attempt,
        action=action,
        success=success,
        details=result,
        timestamp=datetime.utcnow()
    )
    
    if success:
        return {
            "fix_attempts": [fix_attempt],
            "current_attempt": current_attempt,
            "status": ResolutionStatus.RESOLVED,
            "resolution_summary": f"Auto-fixed via {action}",
            "next_agent": "complete",
            "messages": [{"role": "fix", "content": f"✅ Fix successful: {result}"}]
        }
    else:
        next_agent = "diagnostic" if current_attempt < state["max_attempts"] else "escalate"
        return {
            "fix_attempts": [fix_attempt],
            "current_attempt": current_attempt,
            "next_agent": next_agent,
            "messages": [{"role": "fix", "content": f"❌ Fix failed: {result}"}]
        }


# ============== ESCALATION AGENT ==============

async def escalation_agent(state: AutoResolveState) -> dict:
    """Prepare escalation context for human intervention"""
    issue = state["issue"]
    triage = state.get("triage_result")
    diagnostic = state.get("diagnostic_result")
    
    summary = f"""
🚨 ESCALATION REQUIRED

Issue: {issue.title}
Severity: {triage.severity.value if triage else 'Unknown'}
Type: {triage.issue_type.value if triage else 'Unknown'}

Root Cause: {diagnostic.root_cause if diagnostic else 'Unable to determine'}

Fix Attempts: {len(state['fix_attempts'])}
{chr(10).join(f"  - Attempt {f.attempt_number}: {f.action} - {'Success' if f.success else 'Failed'}" for f in state['fix_attempts'])}

Recommended Next Steps:
1. Check application logs for errors
2. Review recent deployments
3. Check resource utilization in Grafana
    """
    
    print(summary)  # In production, send to Slack/PagerDuty
    
    return {
        "status": ResolutionStatus.ESCALATED,
        "resolution_summary": "Escalated to human operator",
        "next_agent": "complete",
        "messages": [{"role": "escalation", "content": summary}]
    }
