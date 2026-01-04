from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple


@dataclass(frozen=True)
class AddCommand:
    task_text: str
    start_dt: datetime
    coins: int
    repeat_unit: str   # "once" | "day" | "week" | "month"
    repeat_every: int  # N >= 1


class AddCommandParser:
    @staticmethod
    def parse_repeat(token: Optional[str]) -> Tuple[str, int]:
        """
        Поддержка:
          once
          daily
          weekly
          monthly
          every:Nd  (например every:3d)
          every:Nw  (например every:2w)
          every:Nm  (например every:3m)
        """
        if not token:
            return "day", 1

        t = token.strip().lower()

        if t == "once":
            return "once", 1
        if t == "daily":
            return "day", 1
        if t == "weekly":
            return "week", 1
        if t == "monthly":
            return "month", 1

        if t.startswith("every:"):
            body = t.split("every:", 1)[1].strip()
            if len(body) < 2:
                raise ValueError("bad repeat")

            unit = body[-1]
            num = body[:-1]

            try:
                n = int(num)
            except ValueError:
                raise ValueError("bad repeat")

            if n < 1:
                raise ValueError("bad repeat")

            if unit == "d":
                return "day", n
            if unit == "w":
                return "week", n
            if unit == "m":
                return "month", n

        raise ValueError("bad repeat")

    @staticmethod
    def parse(message_text: str) -> AddCommand:
        """
        Форматы:

        1) Без даты:
           /add <task...> <HH:MM> <coins> [daily|weekly|monthly|once|every:Nd|every:Nw|every:Nm]
           По умолчанию: daily (day,1)

        2) С датой:
           /add <task...> <YYYY-MM-DD> <HH:MM> <coins> [repeat]
           Если repeat не указан: once
        """
        parts = (message_text or "").split(maxsplit=1)
        if len(parts) < 2:
            raise ValueError("empty")

        payload = parts[1].strip()
        tokens = payload.split()
        if len(tokens) < 3:
            raise ValueError("too few")

        # repeat_token: последний токен, если он не число (coins)
        repeat_token = None
        try:
            int(tokens[-1])
        except ValueError:
            repeat_token = tokens[-1]
            tokens = tokens[:-1]

        if len(tokens) < 3:
            raise ValueError("too few")

        # coins
        try:
            coins = int(tokens[-1])
        except ValueError:
            raise ValueError("bad coins")

        # time
        time_str = tokens[-2]
        try:
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            raise ValueError("bad time")

        # optional date
        date_str = None
        if len(tokens) >= 4:
            cand_date = tokens[-3]
            try:
                datetime.strptime(cand_date, "%Y-%m-%d")
                date_str = cand_date
                task_tokens = tokens[:-3]
            except ValueError:
                task_tokens = tokens[:-2]
        else:
            task_tokens = tokens[:-2]

        task_text = " ".join(task_tokens).strip()
        if not task_text:
            raise ValueError("empty task")

        now = datetime.now()

        if date_str:
            # если дата указана и repeat не указан — по умолчанию once
            repeat_unit, repeat_every = ("once", 1) if not repeat_token else AddCommandParser.parse_repeat(repeat_token)
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            return AddCommand(task_text, start_dt, coins, repeat_unit, repeat_every)

        # без даты: repeat по умолчанию daily
        repeat_unit, repeat_every = AddCommandParser.parse_repeat(repeat_token) if repeat_token else ("day", 1)

        today = now.strftime("%Y-%m-%d")
        start_dt = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M")
        if start_dt < now:
            start_dt = start_dt + timedelta(days=1)

        return AddCommand(task_text, start_dt, coins, repeat_unit, repeat_every)


def format_repeat(repeat_unit: str, repeat_every: int) -> str:
    unit = (repeat_unit or "").lower()
    every = int(repeat_every or 1)

    if unit == "once":
        return "once"
    if unit == "day":
        return "daily" if every == 1 else f"every:{every}d"
    if unit == "week":
        return "weekly" if every == 1 else f"every:{every}w"
    if unit == "month":
        return "monthly" if every == 1 else f"every:{every}m"

    return "-"
