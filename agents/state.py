"""AutoResolve - State Definitions for LangGraph"""
from typing import TypedDict, Annotated, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import operator


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    NONE = "none"


class IssueType(str, Enum):
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    HIGH_ERROR_RATE = "high_error_rate"
    POD_CRASH = "pod_crash"
    UNKNOWN = "unknown"


class ResolutionStatus(str, Enum):
    DETECTED = "detected"
    TRIAGING = "triaging"
    DIAGNOSING = "diagnosing"
    FIXING = "fixing"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class Issue(BaseModel):
    id: str
    title: str
    description: str
    severity: Severity
    service_name: str
    namespace: str = "default"
    labels: dict = Field(default_factory=dict)
    annotations: dict = Field(default_factory=dict)
    started_at: str
    raw_data: dict = Field(default_factory=dict)


class TriageResult(BaseModel):
    issue_type: IssueType
    severity: Severity
    confidence: float
    reasoning: str
    recommended_action: str


class DiagnosticResult(BaseModel):
    root_cause: str
    affected_pods: list[str]
    is_auto_fixable: bool
    fix_action: str
    confidence: float


class FixAttempt(BaseModel):
    attempt_number: int
    action: str
    success: bool
    details: str
    timestamp: datetime


class AutoResolveState(TypedDict):
    """Main state flowing through the agent graph"""
    issue: Issue
    triage_result: Optional[TriageResult]
    diagnostic_result: Optional[DiagnosticResult]
    fix_attempts: Annotated[list[FixAttempt], operator.add]
    current_attempt: int
    max_attempts: int
    status: ResolutionStatus
    resolution_summary: Optional[str]
    next_agent: str
    messages: Annotated[list[dict], operator.add]
