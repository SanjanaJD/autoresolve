"""Kubernetes Tools for Agents"""
from langchain_core.tools import tool
from kubernetes import client, config
import json

# Load kubeconfig
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()


@tool
def get_pod_status(namespace: str = "default", label_selector: str = None) -> str:
    """Get status of pods in a namespace. Returns pod names, status, and restart counts."""
    try:
        pods = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        result = []
        for pod in pods.items:
            containers = pod.status.container_statuses or []
            result.append({
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "ready": all(c.ready for c in containers),
                "restarts": sum(c.restart_count for c in containers)
            })
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def get_pod_logs(pod_name: str, namespace: str = "default", tail_lines: int = 50) -> str:
    """Get logs from a specific pod. Useful for diagnosing application errors."""
    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines
        )
        return logs
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def get_kubernetes_events(namespace: str = "default") -> str:
    """Get recent Kubernetes events. Shows warnings, errors, and state changes."""
    try:
        events = v1.list_namespaced_event(namespace=namespace)
        result = []
        for e in sorted(events.items, key=lambda x: x.last_timestamp or x.event_time or "", reverse=True)[:10]:
            result.append({
                "type": e.type,
                "reason": e.reason,
                "message": e.message,
                "object": f"{e.involved_object.kind}/{e.involved_object.name}",
                "count": e.count
            })
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def restart_deployment(deployment_name: str, namespace: str = "default") -> str:
    """Restart a deployment by triggering a rolling update. Use for stuck pods or memory issues."""
    try:
        from datetime import datetime
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat()
                        }
                    }
                }
            }
        }
        apps_v1.patch_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            body=patch
        )
        return f"✅ Successfully restarted deployment {deployment_name}"
    except Exception as e:
        return f"❌ Failed to restart: {str(e)}"


@tool
def rollback_deployment(deployment_name: str, namespace: str = "default") -> str:
    """Rollback a deployment to the previous version. Use when recent deployment caused issues."""
    try:
        import subprocess
        result = subprocess.run(
            ["kubectl", "rollout", "undo", f"deployment/{deployment_name}", "-n", namespace],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return f"✅ Successfully rolled back {deployment_name}"
        return f"❌ Rollback failed: {result.stderr}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def scale_deployment(deployment_name: str, replicas: int, namespace: str = "default") -> str:
    """Scale a deployment to specified replicas. Use for resource issues."""
    if replicas < 1 or replicas > 10:
        return "❌ Replicas must be between 1 and 10"
    try:
        apps_v1.patch_namespaced_deployment_scale(
            name=deployment_name,
            namespace=namespace,
            body={"spec": {"replicas": replicas}}
        )
        return f"✅ Scaled {deployment_name} to {replicas} replicas"
    except Exception as e:
        return f"❌ Failed to scale: {str(e)}"


# Export all tools
K8S_TOOLS = [
    get_pod_status,
    get_pod_logs,
    get_kubernetes_events,
    restart_deployment,
    rollback_deployment,
    scale_deployment
]
