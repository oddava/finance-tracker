from typing import Dict
from bot.database import User


def get_menu_text() -> str:
    """Display main menu with all options"""

    return (
        "🏠 <b>Main Menu</b>\n\n"
        "What would you like to do?\n\n"
        "<b>Quick Commands:</b>\n"
        "• Just type: <code>50k taxi</code>\n"
        "• /today - Today's summary\n"
        "• /recent - Recent transactions\n"
        "• /help - Get help"
    )

def get_help_text() -> str:
    return (
        "❓ <b>How to Use Finance Tracker Bot</b>\n\n"

        "<b>📝 Logging Expenses:</b>\n"
        "• Natural: <code>50k taxi</code>\n"
        "• Natural: <code>lunch 25000</code>\n"
        "• Natural: <code>spent 150 on groceries</code>\n"

        "<b>📊 View Reports:</b>\n"
        "• /today - Today's expenses\n"
        "• /week [soon] - This week's summary\n"
        "• /month [soon] - Monthly breakdown\n"
        "• /recent - Last 10 transactions\n\n"

        "<b>🎯 Budgets [soon]:</b>\n"
        "• /budget - Set/view budgets\n"
        "• /budgets - All budgets status\n\n"

        "<b>⚙️ Settings [soon]:</b>\n"
        "• /settings - Change preferences\n"
        "• /currency - Change currency\n"
        "• /categories - Manage categories\n\n"

        "<b>📈 Analytics [soon]:</b>\n"
        "• /insights - AI-powered insights\n"
        "• /compare - Compare periods\n"
        "• /export - Export data to Excel\n\n"

        "<b>📚 Other:</b>\n"
        "• /about - About the bot\n"
        "• /feedback - Report issues\n\n"
    )

def get_about_text(user: User, monthly_summary: Dict) -> str:
    return (
        "ℹ️ <b>About Finance Tracker Bot</b>\n\n"

        "🤖 Smart personal finance tracking made easy!\n\n"

        "<b>Your Stats:</b>\n"
        f"📅 Member since: {user.created_at.strftime('%d %b %Y')}\n"
        f"💰 Currency: {user.currency}\n"
        f"📝 This month: {monthly_summary['transaction_count']} transactions\n"
        f"💸 Total spent: {monthly_summary['total_expenses']:,.0f} {user.currency}\n\n"

        "<b>Features:</b>\n"
        "✅ Natural language expense logging\n"
        "✅ Budget tracking & alerts\n"
        "✅ Smart insights & analytics\n"
        "✅ Visual reports & charts\n"
        "✅ Multiple currencies support\n"
        "✅ Data export (Excel/CSV)\n\n"

        "Made with ❤️\n"
        "Version: 1.0.0"
    )

def get_feedback_text() -> str:
    return (
        "💬 <b>Feedback & Support</b>\n\n"

        "We'd love to hear from you!\n\n"

        "📧 <b>Contact:</b>\n"
        "• Email: oddava@proton.me\n"
        "• Telegram: @notJony\n\n"

        "🐛 <b>Report Issues:</b>\n"
        "Found a bug? Let us know!\n\n"

        "⭐ <b>Feature Requests:</b>\n"
        "Have an idea? We're listening!\n\n"

        "🌟 <b>Rate Us:</b>\n"
        "Enjoying the bot? Share with friends!"
    )