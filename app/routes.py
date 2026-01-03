from telegram.ext import CommandHandler, CallbackQueryHandler


def register_routes(application, c):
    # user
    application.add_handler(CommandHandler("start", c.tasks_controller.start))
    application.add_handler(CommandHandler("register", c.tasks_controller.register))
    application.add_handler(CommandHandler("whoami", c.tasks_controller.whoami))

    application.add_handler(CommandHandler("add", c.tasks_controller.add))
    application.add_handler(CommandHandler("tasks", c.tasks_controller.tasks))
    application.add_handler(CommandHandler("done", c.tasks_controller.done))
    application.add_handler(CommandHandler("balance", c.tasks_controller.balance))
    application.add_handler(CommandHandler("history", c.tasks_controller.history))

    # help
    application.add_handler(CommandHandler("help", c.help_controller.help_command))
    application.add_handler(CallbackQueryHandler(c.help_controller.help_callback, pattern=r"^help:"))

    # shop
    application.add_handler(CommandHandler("shop", c.shop_controller.shop))
    application.add_handler(CommandHandler("buy", c.shop_controller.buy))
    application.add_handler(CommandHandler("inventory", c.shop_controller.inventory))
    application.add_handler(CommandHandler("use", c.shop_controller.use))

    # admin
    application.add_handler(CommandHandler("genkey", c.admin_controller.genkey))
    application.add_handler(CommandHandler("users", c.admin_controller.users))
    application.add_handler(CommandHandler("addto", c.admin_controller.addto))
    application.add_handler(CommandHandler("delete", c.admin_controller.delete))
    application.add_handler(CommandHandler("edit", c.admin_controller.edit))

    # rewards admin
    application.add_handler(CommandHandler("rewards", c.admin_controller.rewards))
    application.add_handler(CommandHandler("addreward", c.admin_controller.addreward))
    application.add_handler(CommandHandler("rewarddesc", c.admin_controller.rewarddesc))
    application.add_handler(CommandHandler("rewardon", c.admin_controller.rewardon))
    application.add_handler(CommandHandler("rewardoff", c.admin_controller.rewardoff))
