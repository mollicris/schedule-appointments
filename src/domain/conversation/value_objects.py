from enum import Enum


class ConversationState(str, Enum):
    """21-state conversation state machine from the spec."""

    # Entry
    IDLE = "idle"

    # Booking flow
    EXTRACTING_ENTITIES = "extracting_entities"
    CONFIRMING_INFERRED = "confirming_inferred"
    SELECTING_SERVICE = "selecting_service"
    COLLECTING_DYNAMIC_FIELDS = "collecting_dynamic_fields"
    SELECTING_DATE = "selecting_date"
    SELECTING_TIME = "selecting_time"
    SELECTING_PROFESSIONAL = "selecting_professional"
    COLLECTING_NAME = "collecting_name"
    CONFIRMING_APPOINTMENT = "confirming_appointment"

    # Other flows
    CONFIRMING_CANCEL = "confirming_cancel"
    CONFIRMING_RESCHEDULE = "confirming_reschedule"
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_CANCELLED = "appointment_cancelled"

    # Escalation and timeouts
    HUMAN_HANDOVER = "human_handover"
    WAITING_FOR_MORE = "waiting_for_more"
