import firebase_admin
from firebase_admin import credentials, firestore
from config import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        logger.warning(f"Could not initialize Firebase: {e}. Will mock DB calls if missing.")


def get_db():
    if firebase_admin._apps:
        return firestore.client()
    return None


async def update_pipeline_status(run_id: str, status: str, data: dict):
    db = get_db()
    if db:
        try:
            db.collection("pipeline_runs").document(run_id).set({
                "status": status,
                "updated_at": datetime.now().isoformat(),
                **data
            }, merge=True)
        except Exception as e:
            logger.error(f"Firestore update failed: {e}")


async def update_price_record(commodity: str, city: str, alert_active: bool, recommended_action: str):
    doc_id = f"{city}_{commodity}".replace(" ", "_").lower()
    db = get_db()
    if db:
        db.collection("prices").document(doc_id).set({
            "alert_active": alert_active,
            "recommended_action": recommended_action,
            "updated_at": datetime.now().isoformat()
        }, merge=True)
    return {"updated": doc_id, "alert_active": alert_active}


async def log_sms_event(city: str, count: int, mode: str, sid: str):
    db = get_db()
    if db:
        db.collection("sms_events").add({
            "city": city,
            "recipient_count": count,
            "mode": mode,
            "twilio_sid": sid,
            "timestamp": datetime.now().isoformat()
        })

async def get_latest_insights(limit: int = 3) -> list:
    db = get_db()
    if not db:
        return []

    try:
        docs = db.collection("pipeline_runs").order_by(
            "updated_at", direction=firestore.Query.DESCENDING
        ).limit(limit).stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            if "insight" in data and data["insight"]:
                results.append({
                    "run_id": doc.id,
                    "insight": data.get("insight", {}),
                    "actions": data.get("actions", []),
                    "updated_at": data.get("updated_at")
                })
        return results
    except Exception as e:
        logger.error(f"Failed to fetch insights: {e}")
        return []


async def get_latest_actions(limit: int = 20) -> list:
    """Fetch the latest executed actions with SMS messages."""
    db = get_db()
    if not db:
        return []

    try:
        docs = db.collection("pipeline_runs").order_by(
            "updated_at", direction=firestore.Query.DESCENDING
        ).limit(limit).stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            executed = data.get("executed_action")
            result = data.get("execution_result", {})

            if executed:
                message = result.get("sample_output", "")
                # Look for Urdu message in insight if not in sample_output
                if not message or len(message) < 10:
                    insight = data.get("insight", {})
                    message = insight.get("headline_urdu", "")

                results.append({
                    "run_id": doc.id,
                    "action_type": executed.get("action_type", "UNKNOWN"),
                    "title": executed.get("title", ""),
                    "title_urdu": executed.get("title_urdu", ""),
                    "city": executed.get("target", {}).get("city", ""),
                    "message": message,
                    "recipient_count": executed.get("target", {}).get("count", 0),
                    "timestamp": data.get("updated_at"),
                    "status": result.get("execution_status", "unknown")
                })
        return results
    except Exception as e:
        logger.error(f"Failed to fetch actions: {e}")
        return []


async def get_latest_prices() -> dict:
    """Fetch the latest parsed prices organized by city."""
    db = get_db()
    if not db:
        return {}

    try:
        # Get latest pipeline run with prices
        docs = db.collection("pipeline_runs").order_by(
            "updated_at", direction=firestore.Query.DESCENDING
        ).limit(1).stream()

        for doc in docs:
            data = doc.to_dict()
            raw_prices = data.get("raw_prices", [])
            return {"prices": raw_prices, "updated_at": data.get("updated_at")}

        return {"prices": [], "updated_at": None}
    except Exception as e:
        logger.error(f"Failed to fetch prices: {e}")
        return {"prices": [], "updated_at": None}