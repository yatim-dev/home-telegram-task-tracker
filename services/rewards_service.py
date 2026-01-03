from repos.shop_repo import ShopRepo


class RewardsService:
    def __init__(self, shop: ShopRepo):
        self.shop = shop

    async def list_all(self):
        return await self.shop.list_rewards_admin()

    async def add_reward(self, title: str, price: int, description: str = "") -> int:
        return await self.shop.add_reward(title, description, price)

    async def set_desc(self, reward_id: int, description: str) -> bool:
        return bool(await self.shop.set_reward_description(reward_id, description))

    async def set_active(self, reward_id: int, is_active: int) -> bool:
        return bool(await self.shop.set_reward_active(reward_id, is_active))
