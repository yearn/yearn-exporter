import os
import traceback
from datetime import datetime
from brownie import chain
from telegram.error import BadRequest
from y import Network

def monitoring(script, export_mode_import):
    if os.getenv("DEBUG", None):
        main()
        return
    from telegram.ext import Updater

    export_mode =  export_mode_import
    private_group = os.environ.get('TG_YFIREBOT_GROUP_INTERNAL')
    public_group = os.environ.get('TG_YFIREBOT_GROUP_EXTERNAL')
    updater = Updater(os.environ.get('TG_YFIREBOT'))
    now = datetime.now()

    if script == "s3":
      message = f"`[{now}]`\n⚙️ #{export_mode} Vaults API for #{Network.name()} is updating..."
      ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
      ping = ping.message_id
      try:
          main()
      except Exception as error:
          tb = traceback.format_exc()
          now = datetime.now()
          message = f"`[{now}]`\n🔥 #{export_mode} Vaults API update for #{Network.name()} failed!\n"
          if chain.id == Network.Mainnet:
              return
          else:
              try:
                  detail_message = (message + f"```\n{tb}\n```")[:4000]
                  updater.bot.send_message(chat_id=private_group, text=detail_message, parse_mode="Markdown", reply_to_message_id=ping)
                  updater.bot.send_message(chat_id=public_group, text=detail_message, parse_mode="Markdown")
              except BadRequest:
                  detail_message = message + f"{error.__class__.__name__}({error})"
                  updater.bot.send_message(chat_id=private_group, text=detail_message, parse_mode="Markdown", reply_to_message_id=ping)
                  updater.bot.send_message(chat_id=public_group, text=detail_message, parse_mode="Markdown")
              raise error
      message = f"✅ #{export_mode} Vaults API update for #{Network.name()} successful!"
      updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)
    elif script == "revenues":
      message = f"`[{now}]`\n⚙️ Revenues script for ZooTroop is collecting to send..."
      ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
      ping = ping.message_id
      try:
          main()
      except Exception as error:
          tb = traceback.format_exc()
          now = datetime.now()
          message = f"`[{now}]`\n🔥 Revenues script for ZooTroop has failed!\n```\n{tb}\n```"[:4000]
          updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown", reply_to_message_id=ping)
          updater.bot.send_message(chat_id=public_group, text=message, parse_mode="Markdown")
          raise error
      message = f"✅ Revenues script for ZooTroop has sent!"
      updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)
    elif script == "curve_apy_previews":
      message = f"`[{now}]`\n⚙️ Curve Previews API for {Network.name()} is updating..."
      ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
      ping = ping.message_id
      try:
          main()
      except Exception as error:
          tb = traceback.format_exc()
          now = datetime.now()
          message = f"`[{now}]`\n🔥 Curve Previews API update for {Network.name()} failed!\n```\n{tb}\n```"[:4000]
          updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown", reply_to_message_id=ping)
          updater.bot.send_message(chat_id=public_group, text=message, parse_mode="Markdown")
          raise error
      message = f"✅ Curve Previews API update for {Network.name()} successful!"
      updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)
    else:
        message = f"`[{now}]`\n⚙️ Error what script was run?"
        ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
        ping = ping.message_id