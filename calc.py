
import os
import re
import ast
import html
import operator
import logging
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CopyTextButton
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# =====================================
#           PK CALCULATOR
# =====================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

logging.basicConfig(level=logging.ERROR)


# =====================================
#           MATH ENGINE
# =====================================

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculate_node(node):

    if isinstance(node, ast.Expression):
        return calculate_node(node.body)

    if isinstance(node, ast.Constant):
        if type(node.value) in (int, float):
            return node.value
        raise ValueError("Invalid number")

    if isinstance(node, ast.BinOp):

        op = type(node.op)

        if op not in OPS:
            raise ValueError("Invalid operator")

        left = calculate_node(node.left)
        right = calculate_node(node.right)

        if op == ast.Pow and abs(right) > 100:
            raise ValueError("Power too large")

        if op in (ast.Div, ast.FloorDiv, ast.Mod):
            if right == 0:
                raise ZeroDivisionError()

        result = OPS[op](left, right)

        if isinstance(result, complex):
            raise ValueError("Invalid result")

        if abs(result) > 1e100:
            raise ValueError("Result too large")

        return result

    if isinstance(node, ast.UnaryOp):

        op = type(node.op)

        if op not in OPS:
            raise ValueError("Invalid operator")

        return OPS[op](calculate_node(node.operand))

    raise ValueError("Invalid expression")


def solve(expression):

    expression = expression.strip()

    expression = expression.replace("×", "*")
    expression = expression.replace("÷", "/")
    expression = expression.replace("−", "-")
    expression = expression.replace("–", "-")

    expression = re.sub(
        r"(?<=\d),(?=\d{3}(?:\D|$))",
        "",
        expression
    )

    expression = re.sub(
        r"(\d+(?:\.\d+)?)\s*%",
        r"(\1/100)",
        expression
    )

    expression = re.sub(
        r"\bof\b",
        "*",
        expression,
        flags=re.I
    )

    if not re.fullmatch(
        r"[0-9\s.+\-*/()%]+",
        expression
    ):
        raise ValueError("Invalid characters")

    tree = ast.parse(expression, mode="eval")

    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError("Expression too long")

    return calculate_node(tree)


# =====================================
#          ANSWER FORMAT
# =====================================

def format_answer(number):

    if isinstance(number, float):

        if number.is_integer():
            return str(int(number))

        return f"{number:.12g}"

    return str(number)


# =====================================
#       EXTRACT CALCULATIONS
# =====================================

def extract_calculations(text):

    results = []
    seen = set()

    pattern = (
        r"(?<![\w.])"
        r"[\d(][\d\s,.()+\-*/%×÷−–]*"
        r"[\d)%]"
        r"(?![\w.])"
    )

    for line in text.splitlines():

        line = re.sub(
            r"^\s*(?:\d+[.)]|[-•])\s*",
            "",
            line
        )

        parts = re.split(r"[;|]", line)

        for part in parts:

            for match in re.finditer(pattern, part):

                expression = match.group().strip()

                if not re.search(
                    r"[+\-*/%×÷−–]",
                    expression
                ):
                    continue

                try:
                    answer = solve(expression)

                    key = (expression, str(answer))

                    if key not in seen:

                        seen.add(key)

                        results.append(
                            (expression, answer)
                        )

                except Exception:
                    continue

    return results[:20]


# =====================================
#              IMAGE OCR
# =====================================

# =====================================
#             START
# =====================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.effective_message.reply_text(
        "🧮 PK CALCULATOR\n\n"
        "⚡ Instant Mathematical Calculator\n\n"
        "Send any mathematical calculation.\n"
        "Get your answer instantly.\n\n"
        "➕ Addition\n"
        "➖ Subtraction\n"
        "✖️ Multiplication\n"
        "➗ Division\n"
        "％ Percentage\n\n"
        "Fast • Simple • Smart"
    )


# =====================================
#              HELP
# =====================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.effective_message.reply_text(
        "🧮 PK CALCULATOR\n\n"
        "Send mathematical calculations directly.\n\n"
        "Examples:\n"
        "500+200\n"
        "450×25\n"
        "15000/25\n"
        "20% of 500\n\n"
        "Multiple calculations can be sent "
        "on separate lines."
    )


# =====================================
#          MESSAGE HANDLER
# =====================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.effective_message

    if not message:
        return

    text_content = message.text or message.caption or ""

    if not text_content.strip():
        return

    calculations = extract_calculations(text_content)

    if not calculations:
        return

    # SINGLE CALCULATION
    if len(calculations) == 1:

        expression, answer = calculations[0]

        formatted = format_answer(answer)

        result_text = (
            "🧮 <b>PK CALCULATOR</b>\n\n"
            f"<b>{html.escape(formatted)}</b>"
        )

        copy_value = formatted
        button_text = "📋 Copy Answer"

    # MULTIPLE CALCULATIONS
    else:

        lines = []
        copy_values = []

        for index, (expression, answer) in enumerate(
            calculations, start=1
        ):

            formatted = format_answer(answer)

            lines.append(
                f"<b>{index}.</b> "
                f"<b>{html.escape(formatted)}</b>"
            )

            copy_values.append(formatted)

        result_text = (
            "🧮 <b>PK CALCULATOR</b>\n\n"
            + "\n".join(lines)
        )

        copy_value = "\n".join(copy_values)
        button_text = "📋 Copy All Answers"

    # COPY BUTTON
    keyboard = None

    if len(copy_value) <= 256:

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                text=button_text,
                copy_text=CopyTextButton(
                    text=copy_value
                )
            )
        ]])

    await message.reply_text(
        result_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =====================================
#               MAIN
# =====================================

def main():

    if BOT_TOKEN == "YOUR_BOT_TOKEN":
        raise ValueError("Set your BOT_TOKEN first")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_message
        )
    )

    print("================================")
    print("       PK CALCULATOR")
    print("       BOT STARTED")
    print("================================")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()

