from repos.users_repo import UsersRepo
from repos.shop_repo import ShopRepo


class ShopService:
    def __init__(self, users: UsersRepo, shop: ShopRepo):
        self.users = users
        self.shop = shop

    async def list_shop(self):
        return await self.shop.list_rewards(active_only=True)

    async def buy(self, user_id: int, reward_id: int):
        return await self.shop.buy_reward(user_id, reward_id)

    async def inventory(self, user_id: int):
        return await self.shop.get_inventory(user_id)

    async def use(self, user_id: int, purchase_id: int):
        ok, title, price = await self.shop.use_purchase_with_info(user_id, purchase_id)
        admin_ids = await self.users.list_admin_ids()
        return ok, title, price, admin_ids
