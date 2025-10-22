"""
Text formatting utilities
"""
from datetime import datetime


def format_amount(amount: float, currency: str = "UZS") -> str:
    """
    Format amount with currency symbol

    Args:
        amount: Amount to format
        currency: Currency code

    Returns:
        Formatted string like "50,000 UZS" or "$50.00"
    """
    # Currency symbols
    symbols = {
        "UZS": "so'm",
        "USD": "$",
        "EUR": "€",
        "RUB": "₽",
        "GBP": "£"
    }

    symbol = symbols.get(currency, currency)

    # For UZS, no decimals and use comma separator
    if currency == "UZS":
        formatted = f"{int(amount):,}".replace(",", " ")
        return f"{formatted} {symbol}"

    # For other currencies, use 2 decimals
    if symbol in ["$", "€", "£", "₽"]:
        return f"{symbol}{amount:,.2f}"

    return f"{amount:,.2f} {symbol}"


def format_transaction_message(transaction, category, currency: str) -> str:
    """
    Format a transaction as a message

    Args:
        transaction: Transaction object
        category: Category object
        currency: User's currency

    Returns:
        Formatted message string
    """
    type_emoji = "💸" if transaction.type == "expense" else "💰"

    message = f"{type_emoji} <b>{category.icon_emoji} {format_amount(transaction.amount, currency)}</b>\n"
    message += f"Category: {category.name}\n"

    if transaction.description:
        message += f"Note: {transaction.description}\n"

    message += f"Date: {transaction.date.strftime('%d %b %Y, %H:%M')}\n"
    message += f"Method: {transaction.payment_method.title()}"

    return message


def format_date_range(start_date: datetime, end_date: datetime) -> str:
    """Format a date range"""
    if start_date.date() == end_date.date():
        return start_date.strftime("%d %B %Y")

    if start_date.year == end_date.year:
        if start_date.month == end_date.month:
            return f"{start_date.day}-{end_date.day} {start_date.strftime('%B %Y')}"
        return f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"

    return f"{start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}"


def format_percentage(value: float, total: float) -> str:
    """Format a percentage with proper handling of edge cases"""
    if total == 0:
        return "0%"

    percentage = (value / total) * 100
    return f"{percentage:.1f}%"


def format_progress_bar(current: float, target: float, length: int = 10) -> str:
    """
    Create a progress bar

    Args:
        current: Current value
        target: Target value
        length: Length of progress bar in characters

    Returns:
        Progress bar string like "████████░░ 80%"
    """
    if target == 0:
        return "░" * length + " 0%"

    percentage = min(current / target, 1.0)
    filled = int(length * percentage)
    empty = length - filled

    bar = "█" * filled + "░" * empty
    percent_text = f"{percentage * 100:.0f}%"

    return f"{bar} {percent_text}"


def format_budget_status(spent: float, budget: float, currency: str) -> str:
    """
    Format budget status message

    Args:
        spent: Amount spent
        budget: Budget amount
        currency: Currency code

    Returns:
        Formatted status message
    """
    percentage = (spent / budget * 100) if budget > 0 else 0
    remaining = budget - spent

    # Choose emoji based on status
    if percentage >= 100:
        emoji = "🔴"
        status = "Exceeded"
    elif percentage >= 80:
        emoji = "🟠"
        status = "Warning"
    elif percentage >= 50:
        emoji = "🟡"
        status = "On Track"
    else:
        emoji = "🟢"
        status = "Good"

    message = f"{emoji} <b>{status}</b>\n"
    message += f"Spent: {format_amount(spent, currency)}\n"
    message += f"Budget: {format_amount(budget, currency)}\n"
    message += f"Remaining: {format_amount(remaining, currency)}\n"
    message += f"\n{format_progress_bar(spent, budget)}"

    return message