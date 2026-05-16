from enum import Enum


class DayOfWeek(str, Enum):
    MONDAY = "0"
    TUESDAY = "1"
    WEDNESDAY = "2"
    THURSDAY = "3"
    FRIDAY = "4"
    SATURDAY = "5"
    SUNDAY = "6"


class BusinessStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
