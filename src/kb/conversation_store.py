"""
Conversation store for managing multi-turn conversation threads.
Enables Q&A follow-up by preserving context across ticket interactions.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..schemas import (
    SupportTicket, PipelineResult, ExtractedFields, TriageResult, RoutingDecision,
    Conversation, ConversationMessage, ConversationStatus, ConversationInfo, AccountTier
)


class ConversationStore:
    """
    Manages conversation threads across ticket follow-ups.
    Stores conversations as JSON files for simplicity (can be upgraded to DB).
    """

    def __init__(self, persist_dir: str | Path | None = None):
        """
        Initialize the conversation store.

        Args:
            persist_dir: Directory to persist conversation data
        """
        if persist_dir is None:
            from .indexer import get_data_path
            persist_dir = get_data_path() / "conversations"

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of conversations
        self._conversations: dict[str, Conversation] = {}
        self._load_all_conversations()

    def _get_conversation_path(self, conversation_id: str) -> Path:
        """Get the file path for a conversation."""
        return self.persist_dir / f"{conversation_id}.json"

    def _load_all_conversations(self) -> None:
        """Load all conversations from disk into memory."""
        for conv_file in self.persist_dir.glob("*.json"):
            try:
                with open(conv_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                conv = Conversation(**data)
                self._conversations[conv.conversation_id] = conv
            except Exception as e:
                print(f"Warning: Failed to load conversation {conv_file}: {e}")

    def _save_conversation(self, conversation: Conversation) -> None:
        """Save a conversation to disk."""
        path = self._get_conversation_path(conversation.conversation_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conversation.model_dump(mode="json"), f, indent=2, default=str)

    def create_conversation(
        self,
        ticket: SupportTicket,
        triage: TriageResult,
        extracted: ExtractedFields,
        routing: RoutingDecision
    ) -> Conversation:
        """
        Create a new conversation from an initial ticket.

        Args:
            ticket: The initial support ticket
            triage: Triage results
            extracted: Extracted fields
            routing: Routing decision

        Returns:
            The created Conversation
        """
        conversation_id = f"conv-{ticket.ticket_id}"

        # Create initial message from ticket
        initial_message = ConversationMessage(
            message_id=ticket.ticket_id,
            timestamp=ticket.created_at,
            sender_type="customer",
            sender_id=ticket.customer_email,
            content=f"Subject: {ticket.subject}\n\n{ticket.body}",
            extracted_fields=extracted,
            is_auto_reply=False
        )

        # Determine initial status based on whether we need more info
        if extracted.missing_fields:
            status = ConversationStatus.awaiting_customer
        else:
            status = ConversationStatus.in_progress

        conversation = Conversation(
            conversation_id=conversation_id,
            original_ticket_id=ticket.ticket_id,
            customer_email=ticket.customer_email,
            customer_name=ticket.customer_name,
            account_tier=ticket.account_tier,
            product=ticket.product,
            subject=ticket.subject,
            messages=[initial_message],
            status=status,
            pending_fields=extracted.missing_fields.copy(),
            merged_extracted_fields=extracted,
            current_triage=triage,
            current_routing=routing,
            created_at=ticket.created_at,
            updated_at=datetime.now()
        )

        self._conversations[conversation_id] = conversation
        self._save_conversation(conversation)

        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: The conversation ID

        Returns:
            The Conversation or None if not found
        """
        return self._conversations.get(conversation_id)

    def add_customer_message(
        self,
        conversation_id: str,
        ticket: SupportTicket,
        extracted: ExtractedFields
    ) -> Optional[Conversation]:
        """
        Add a follow-up message from the customer to a conversation.

        Args:
            conversation_id: The conversation ID
            ticket: The follow-up ticket
            extracted: Fields extracted from the follow-up

        Returns:
            Updated Conversation or None if not found
        """
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return None

        # Create message from follow-up
        message = ConversationMessage(
            message_id=ticket.ticket_id,
            timestamp=ticket.created_at,
            sender_type="customer",
            sender_id=ticket.customer_email,
            content=ticket.body,
            extracted_fields=extracted,
            is_auto_reply=False
        )

        conversation.messages.append(message)
        conversation.updated_at = datetime.now()

        # Merge extracted fields
        self._merge_extracted_fields(conversation, extracted)

        # Update pending fields
        self._update_pending_fields(conversation)

        # Update status
        if not conversation.pending_fields:
            conversation.status = ConversationStatus.in_progress
        else:
            conversation.status = ConversationStatus.awaiting_customer

        self._save_conversation(conversation)
        return conversation

    def add_system_reply(
        self,
        conversation_id: str,
        reply_content: str,
        is_auto_reply: bool = False
    ) -> Optional[Conversation]:
        """
        Add a system/agent reply to the conversation.

        Args:
            conversation_id: The conversation ID
            reply_content: The reply content
            is_auto_reply: Whether this is an automated reply

        Returns:
            Updated Conversation or None if not found
        """
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return None

        message = ConversationMessage(
            message_id=f"reply-{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            sender_type="system" if is_auto_reply else "agent",
            sender_id="system",
            content=reply_content,
            is_auto_reply=is_auto_reply
        )

        conversation.messages.append(message)
        conversation.updated_at = datetime.now()

        self._save_conversation(conversation)
        return conversation

    def _merge_extracted_fields(
        self,
        conversation: Conversation,
        new_extraction: ExtractedFields
    ) -> None:
        """
        Merge newly extracted fields into the conversation's merged fields.
        New values override None values but don't replace existing values.
        """
        if conversation.merged_extracted_fields is None:
            conversation.merged_extracted_fields = new_extraction
            return

        merged = conversation.merged_extracted_fields

        # Merge each field - new value fills in if current is None
        if new_extraction.environment and not merged.environment:
            merged.environment = new_extraction.environment
        if new_extraction.region and not merged.region:
            merged.region = new_extraction.region
        if new_extraction.error_message and not merged.error_message:
            merged.error_message = new_extraction.error_message
        if new_extraction.reproduction_steps and not merged.reproduction_steps:
            merged.reproduction_steps = new_extraction.reproduction_steps
        if new_extraction.impact and not merged.impact:
            merged.impact = new_extraction.impact
        if new_extraction.requested_action and not merged.requested_action:
            merged.requested_action = new_extraction.requested_action
        if new_extraction.order_id and not merged.order_id:
            merged.order_id = new_extraction.order_id

        # Update missing fields based on what we now have
        merged.missing_fields = new_extraction.missing_fields

    def _update_pending_fields(self, conversation: Conversation) -> None:
        """Update the list of pending fields based on merged extraction."""
        if not conversation.merged_extracted_fields:
            return

        merged = conversation.merged_extracted_fields
        still_missing = []

        for field in conversation.pending_fields:
            # Check if the field is still missing
            field_value = getattr(merged, field, None)
            if field_value is None:
                still_missing.append(field)

        conversation.pending_fields = still_missing

    def get_conversation_context(self, conversation_id: str) -> str:
        """
        Get the full conversation history as a formatted string for LLM context.

        Args:
            conversation_id: The conversation ID

        Returns:
            Formatted conversation history
        """
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return ""

        context_parts = [
            f"Conversation ID: {conversation.conversation_id}",
            f"Customer: {conversation.customer_name} ({conversation.customer_email})",
            f"Account Tier: {conversation.account_tier.value}",
            f"Product: {conversation.product}",
            f"Subject: {conversation.subject}",
            f"Status: {conversation.status.value}",
            "",
            "--- Message History ---"
        ]

        for msg in conversation.messages:
            sender_label = msg.sender_type.upper()
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
            context_parts.append(f"\n[{sender_label}] ({timestamp})")
            context_parts.append(msg.content)

            if msg.extracted_fields:
                fields = msg.extracted_fields
                extracted = []
                if fields.environment:
                    extracted.append(f"environment={fields.environment}")
                if fields.region:
                    extracted.append(f"region={fields.region}")
                if fields.error_message:
                    extracted.append(f"error={fields.error_message[:50]}...")
                if fields.order_id:
                    extracted.append(f"order_id={fields.order_id}")
                if extracted:
                    context_parts.append(f"[Extracted: {', '.join(extracted)}]")

        if conversation.pending_fields:
            context_parts.append(f"\n--- Still Needed: {', '.join(conversation.pending_fields)} ---")

        return "\n".join(context_parts)

    def get_merged_fields(self, conversation_id: str) -> Optional[ExtractedFields]:
        """Get the merged extracted fields for a conversation."""
        conversation = self._conversations.get(conversation_id)
        if conversation:
            return conversation.merged_extracted_fields
        return None

    def update_triage(
        self,
        conversation_id: str,
        triage: TriageResult,
        routing: RoutingDecision
    ) -> Optional[Conversation]:
        """Update the triage and routing for a conversation."""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return None

        conversation.current_triage = triage
        conversation.current_routing = routing
        conversation.updated_at = datetime.now()

        self._save_conversation(conversation)
        return conversation

    def resolve_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Mark a conversation as resolved."""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return None

        conversation.status = ConversationStatus.resolved
        conversation.resolved_at = datetime.now()
        conversation.updated_at = datetime.now()

        self._save_conversation(conversation)
        return conversation

    def get_conversations_by_customer(self, customer_email: str) -> list[Conversation]:
        """Get all conversations for a customer."""
        return [
            conv for conv in self._conversations.values()
            if conv.customer_email == customer_email
        ]

    def get_active_conversations(self) -> list[Conversation]:
        """Get all active (non-resolved, non-closed) conversations."""
        active_statuses = {
            ConversationStatus.awaiting_customer,
            ConversationStatus.awaiting_agent,
            ConversationStatus.in_progress
        }
        return [
            conv for conv in self._conversations.values()
            if conv.status in active_statuses
        ]

    def get_awaiting_customer(self) -> list[Conversation]:
        """Get conversations awaiting customer response."""
        return [
            conv for conv in self._conversations.values()
            if conv.status == ConversationStatus.awaiting_customer
        ]

    def get_conversation_info(self, conversation: Conversation) -> ConversationInfo:
        """Create a ConversationInfo summary for a conversation."""
        return ConversationInfo(
            conversation_id=conversation.conversation_id,
            message_count=len(conversation.messages),
            is_followup=len(conversation.messages) > 1,
            pending_fields=conversation.pending_fields,
            status=conversation.status
        )

    def get_stats(self) -> dict:
        """Get statistics about the conversation store."""
        total = len(self._conversations)
        by_status = {}
        for conv in self._conversations.values():
            status = conv.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total_conversations": total,
            "by_status": by_status,
            "awaiting_customer": by_status.get("awaiting_customer", 0),
            "active": total - by_status.get("resolved", 0) - by_status.get("closed", 0)
        }


# Singleton instance
_conversation_store: ConversationStore | None = None


def get_conversation_store(persist_dir: str | Path | None = None) -> ConversationStore:
    """
    Get or create a singleton ConversationStore instance.

    Args:
        persist_dir: Optional persistence directory

    Returns:
        ConversationStore instance
    """
    global _conversation_store

    if _conversation_store is None:
        _conversation_store = ConversationStore(persist_dir=persist_dir)

    return _conversation_store


def reset_conversation_store() -> None:
    """Reset the singleton conversation store instance."""
    global _conversation_store
    _conversation_store = None
