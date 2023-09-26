
import os
import traceback
from datetime import datetime
from typing import Callable, TypeVar

from y import Network

T = TypeVar('T')

PRIVATE_GROUP = os.environ.get('TG_YFIREBOT_GROUP_INTERNAL')
PUBLIC_GROUP = os.environ.get('TG_YFIREBOT_GROUP_EXTERNAL')


def run_job_with_monitoring(job_name: str, job: Callable[[], T]) -> T:
    """A helper function used when we want to run a job and monitor it via telegram"""
    
    if os.getenv("DEBUG", None):
        return job()
    
    from telegram.ext import Updater
    UPDATER = Updater(os.environ.get('TG_YFIREBOT'))

    now = datetime.now()
    message = f"`[{now}]`\n⚙️ {job_name} for {Network.name()} is updating..."
    ping = UPDATER.bot.send_message(chat_id=PRIVATE_GROUP, text=message, parse_mode="Markdown")
    ping = ping.message_id
    try:
        retval = job()
    except Exception as error:
        tb = traceback.format_exc()
        now = datetime.now()
        message = f"`[{now}]`\n🔥 {job_name} update for {Network.name()} failed!\n```\n{tb}\n```"[:4000]
        UPDATER.bot.send_message(chat_id=PRIVATE_GROUP, text=message, parse_mode="Markdown", reply_to_message_id=ping)
        UPDATER.bot.send_message(chat_id=PUBLIC_GROUP, text=message, parse_mode="Markdown")
        raise error
    message = f"✅ {job_name} update for {Network.name()} successful!"
    UPDATER.bot.send_message(chat_id=PRIVATE_GROUP, text=message, reply_to_message_id=ping)
    return retval