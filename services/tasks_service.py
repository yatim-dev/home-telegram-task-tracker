from datetime import datetime
from repos.users_repo import UsersRepo
from repos.tasks_repo import TasksRepo


class TasksService:
    def __init__(self, users: UsersRepo, tasks: TasksRepo):
        self.users = users
        self.tasks = tasks

    async def activate_by_key(self, user_id: int, key: str) -> str | None:
        role = await self.users.consume_registration_key(key)
        if not role:
            return None
        await self.users.activate_user(user_id, role)
        return role

    async def add_self_task(self, user_id: int, cmd) -> tuple[int, str]:
        # cmd: результат AddCommandParser.parse(...)
        next_due = cmd.start_dt.strftime("%Y-%m-%d %H:%M")
        task_id = await self.tasks.add_task(
            user_id=user_id,
            task=cmd.task_text,
            next_due=next_due,
            coins=cmd.coins,
            repeat_unit=cmd.repeat_unit,
            repeat_every=cmd.repeat_every,
            assigned_by=user_id,
        )
        return task_id, next_due

    async def list_tasks(self, user_id: int, show_all: bool):
        if show_all:
            return await self.tasks.list_tasks(user_id)
        end_of_day = datetime.now().strftime("%Y-%m-%d 23:59")
        return await self.tasks.list_tasks_until(user_id, end_of_day)

    async def complete(self, user_id: int, task_id: int) -> tuple[int | None, int]:
        coins = await self.tasks.complete_task(user_id, task_id)
        balance = await self.users.get_balance(user_id)
        return coins, balance

    async def assign_to_username(self, admin_id: int, username: str, cmd) -> tuple[int, int, str]:
        target_id = await self.users.find_user_id_by_username(username)
        if not target_id:
            raise ValueError("user_not_found")

        next_due = cmd.start_dt.strftime("%Y-%m-%d %H:%M")
        task_id = await self.tasks.add_task(
            user_id=target_id,
            task=cmd.task_text,
            next_due=next_due,
            coins=cmd.coins,
            repeat_unit=cmd.repeat_unit,
            repeat_every=cmd.repeat_every,
            assigned_by=admin_id,
        )
        return task_id, target_id, next_due

    async def edit_task(self, task_id: int, cmd) -> str:
        next_due = cmd.start_dt.strftime("%Y-%m-%d %H:%M")
        updated = await self.tasks.update_task(
            task_id=task_id,
            task=cmd.task_text,
            next_due=next_due,
            coins=cmd.coins,
            repeat_unit=cmd.repeat_unit,
            repeat_every=cmd.repeat_every,
        )
        if not updated:
            raise ValueError("task_not_found")
        return next_due

    async def delete_task(self, task_id: int) -> bool:
        deleted = await self.tasks.delete_task(task_id)
        return bool(deleted)
