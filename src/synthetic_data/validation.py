from __future__ import annotations


def validate_dataset(dataset: dict[str, list[dict]]) -> None:
    account_ids = {r["account_id"] for r in dataset.get("accounts", [])}
    sub_ids = {r["subscription_id"] for r in dataset.get("subscriptions", [])}
    ticket_ids = {r["ticket_id"] for r in dataset.get("support_tickets", [])}

    for sub in dataset.get("subscriptions", []):
        assert sub["account_id"] in account_ids, f"Subscription {sub['subscription_id']} references unknown account {sub['account_id']}"

    for event in dataset.get("subscription_events", []):
        assert event["subscription_id"] in sub_ids, f"Event {event['event_id']} references unknown subscription {event['subscription_id']}"
        assert event["account_id"] in account_ids, f"Event {event['event_id']} references unknown account {event['account_id']}"

    for ticket in dataset.get("support_tickets", []):
        assert ticket["subscription_id"] in sub_ids, f"Ticket {ticket['ticket_id']} references unknown subscription {ticket['subscription_id']}"
        assert ticket["account_id"] in account_ids, f"Ticket {ticket['ticket_id']} references unknown account {ticket['account_id']}"

    for refund in dataset.get("refunds", []):
        assert refund["ticket_id"] in ticket_ids, f"Refund {refund['refund_id']} references unknown ticket {refund['ticket_id']}"
        assert refund["subscription_id"] in sub_ids, f"Refund {refund['refund_id']} references unknown subscription {refund['subscription_id']}"
        assert refund["account_id"] in account_ids, f"Refund {refund['refund_id']} references unknown account {refund['account_id']}"
