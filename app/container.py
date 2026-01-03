from db.sqlite_database import SQLiteDatabase
from bot.async_db import AsyncDB

from repos.users_repo import UsersRepo
from repos.tasks_repo import TasksRepo
from repos.history_repo import HistoryRepo
from repos.shop_repo import ShopRepo

from services.auth_service import AuthService
from services.tasks_service import TasksService
from services.history_service import HistoryService
from services.shop_service import ShopService
from services.rewards_service import RewardsService
from services.reminder_service import ReminderService

from controllers.tasks_controller import TasksController
from controllers.admin_controller import AdminController
from controllers.shop_controller import ShopController

from controllers.help_controller import HelpController


class Container:
    def __init__(self, db_path: str = "tasks.db"):
        sync_db = SQLiteDatabase(db_path)
        self.db = AsyncDB(sync_db)

        # repos
        self.users_repo = UsersRepo(self.db)
        self.tasks_repo = TasksRepo(self.db)
        self.history_repo = HistoryRepo(self.db)
        self.shop_repo = ShopRepo(self.db)

        # services
        self.auth = AuthService(self.users_repo)
        self.tasks_service = TasksService(self.users_repo, self.tasks_repo)
        self.history_service = HistoryService(self.history_repo)
        self.shop_service = ShopService(self.users_repo, self.shop_repo)
        self.rewards_service = RewardsService(self.shop_repo)
        self.reminder_service = ReminderService(self.tasks_repo)

        # controllers
        self.tasks_controller = TasksController(self.auth, self.tasks_service, self.history_service, self.users_repo)
        self.admin_controller = AdminController(self.auth, self.tasks_service, self.rewards_service, self.users_repo)
        self.shop_controller = ShopController(self.auth, self.shop_service)
        self.help_controller = HelpController(self.users_repo)  # HelpController пока использует AsyncDB.get_user
