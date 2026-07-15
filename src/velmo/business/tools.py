"""Outils LangChain de lecture métier + résolution d'identité."""
import logging

from langchain_core.tools import tool

from . import repository as repo

logger = logging.getLogger(__name__)

# Identity is a plain module-level dict (NOT a ContextVar): LangChain tool
# .invoke() runs in a copied context where ContextVar writes don't propagate
# back to the caller. The app is single-threaded on the main thread (see
# global constraints), so a module dict reset per request is correct and safe.
_identity: dict = {}


def set_business_identity(user_id: str, email: str | None = None) -> None:
    _identity.clear()
    _identity.update({"user_id": user_id, "email": email})


def get_discovered_email() -> str | None:
    return _identity.get("email")


def _format_order(o: dict) -> str:
    lines = [f"Commande {o['order_number']} — statut : {o['status']} — "
             f"total : {o['total_eur']:.2f} €"]
    if o.get("placed_at"):
        lines.append(f"Créée le : {o['placed_at']}")
    for it in o.get("items", []):
        lines.append(f"  • {it['quantity']}× {it['name']} ({it['sku']}) "
                     f"à {it['unit_price_eur']:.2f} €")
    ship = o.get("shipment")
    if ship:
        lines.append(f"Livraison : {ship['status']} via {ship['carrier']} "
                     f"(suivi {ship['tracking_number']})")
        if ship.get("estimated_delivery"):
            lines.append(f"Livraison estimée : {ship['estimated_delivery']}")
        if ship.get("delivered_at"):
            lines.append(f"Livrée le : {ship['delivered_at']}")
    return "\n".join(lines)


@tool
def lookup_order(order_number: str) -> str:
    """Récupère le statut, les articles et la livraison d'une commande par son
    numéro (ex. 'CMD-4490')."""
    try:
        o = repo.get_order_by_number(order_number)
    except Exception as e:  # noqa: BLE001
        logger.error(f"lookup_order failed: {e}")
        return "Impossible de consulter cette commande pour le moment."
    if not o:
        return f"Aucune commande {order_number} trouvée."
    return _format_order(o)


@tool
def get_customer_orders(email: str | None = None) -> str:
    """Liste les commandes d'un client.

    Si 'email' est fourni, cherche par email.
    Sinon, utilise le client actuellement lié (numéro client CLI-* ou velmo_user_id)."""
    try:
        customer = None
        if email:
            customer = repo.get_customer_by_email(email)
            if customer:
                _identity["email"] = email
        else:
            user_id = _identity.get("user_id")
            # Try customer_ref first (e.g., CLI-000001)
            if user_id and user_id.startswith("CLI-"):
                customer = repo.get_customer_by_customer_ref(user_id)
            # Fall back to velmo_user_id lookup
            if not customer:
                customer = repo.get_customer_by_velmo_user(user_id)
    except Exception as e:  # noqa: BLE001
        logger.error(f"get_customer_orders failed: {e}")
        return "Impossible de consulter les commandes pour le moment."
    if not customer:
        return ("Aucun client identifié. Donnez-moi votre email ou un numéro "
                "de commande (ex. CMD-4490).")
    try:
        orders = repo.get_orders_for_customer(customer["customer_id"])
    except Exception as e:  # noqa: BLE001
        logger.error(f"get_orders_for_customer failed: {e}")
        return "Impossible de consulter les commandes pour le moment."
    if not orders:
        return f"Aucune commande trouvée pour {customer['full_name']}."
    lines = [f"Commandes de {customer['full_name']} (triées par date décroissante) :"]
    for o in orders:
        lines.append(f"  • {o['order_number']} — {o['status']} — "
                     f"{float(o['total_eur']):.2f} € — {o['placed_at']}")
    return "\n".join(lines)


TOOLS = [lookup_order, get_customer_orders]
