"""AutoResolve - FastAPI Application"""
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AutoResolve Agent API")


# AlertManager webhook payload models
class Alert(BaseModel):
    status: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    startsAt: str
    endsAt: str
    fingerprint: Optional[str] = None


class AlertManagerPayload(BaseModel):
    receiver: str
    status: str
    alerts: List[Alert]
    groupLabels: Dict[str, str]
    commonLabels: Dict[str, str]
    commonAnnotations: Optional[Dict[str, str]] = {}
    externalURL: Optional[str] = None


async def process_alert(alert: Dict):
    """Process an alert through the agent workflow"""
    if alert["labels"].get("alertname") in ["Watchdog", "InfoInhibitor"]:
        return
    from agents.graph import run_autoresolve_workflow
    
    try:
        result = await run_autoresolve_workflow(alert)
        logger.info(f"Workflow completed: {result['status']}")
    except Exception as e:
        logger.error(f"Workflow failed: {e}")


@app.post("/webhook/alertmanager")
async def receive_alert(payload: AlertManagerPayload, background_tasks: BackgroundTasks):
    """Receive webhooks from AlertManager"""
    logger.info(f"Received webhook: {payload.status}, {len(payload.alerts)} alerts")
    
    for alert in payload.alerts:
        if alert.status == "firing":
            logger.info(f"🚨 Alert firing: {alert.labels.get('alertname')}")
            
            alert_data = {
                "id": alert.fingerprint or f"alert-{datetime.utcnow().timestamp()}",
                "title": alert.labels.get("alertname", "Unknown"),
                "description": alert.annotations.get("description", ""),
                "severity": alert.labels.get("severity", "warning"),
                "service_name": alert.labels.get("pod", "demo-app"),
                "namespace": alert.labels.get("namespace", "default"),
                "labels": alert.labels,
                "annotations": alert.annotations,
                "started_at": alert.startsAt
            }
            
            background_tasks.add_task(process_alert, alert_data)
        else:
            logger.info(f"✅ Alert resolved: {alert.labels.get('alertname')}")
    
    return {"status": "received", "processed": len(payload.alerts)}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"service": "AutoResolve Agent API", "version": "1.0.0"}
