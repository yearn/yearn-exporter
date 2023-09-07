import os
import psycopg2
import csv
import boto3
import sentry_sdk
import logging
import yearn
import traceback
from datetime import datetime, timedelta
from y import Network

sentry_sdk.set_tag('script','revenues')
logger = logging.getLogger(__name__)

def main():
    debug = os.getenv("DEBUG", None)

    today = datetime.today()
    from_str = os.getenv("REVENUES_FROM", (today-timedelta(days=7)).strftime('%Y-%m-%d'))
    to_str   = os.getenv("REVENUES_TO", today.strftime('%Y-%m-%d'))
    file_name = f"revenues_{from_str}_{to_str}.csv"
    file_path = f"/tmp/{file_name}"

    _export_data(from_str, to_str, file_path)

    if debug:
        logger.info("Printing CSV file contents of %s", file_path)
        with open(file_path) as file:
            reader = csv.reader(file, delimiter=';', quotechar='"')
            for row in reader:
                print(row)
    else:
        # upload the file to the s3 bucket
        s3_bucket = os.environ.get("REVENUES_S3_BUCKET")
        s3_path = f'{os.environ.get("REVENUES_S3_PATH")}/{file_name}'
        s3 = _get_s3()
        s3.upload_file(
            file_path,
            s3_bucket,
            s3_path,
            ExtraArgs={'ContentType': "application/csv", 'CacheControl': "max-age=1800"},
        )
        logger.info("successfully uploaded file '%s' to '%s'", file_path, s3_path)

        # cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("deleted file '%s'", file_path)


def _export_data(from_str, to_str, file_path):
    sql = f"COPY (\
SELECT * FROM general_ledger \
WHERE timestamp::date BETWEEN '{from_str}' AND '{to_str}' ORDER BY timestamp\
) TO STDOUT WITH CSV DELIMITER ';' HEADER QUOTE AS '\"'"

    conn = _get_db_connection()
    with open(file_path, "w") as file:
        cur = conn.cursor()
        cur.copy_expert(sql, file)
    conn.close()
    logger.info("Exported revenues data from '%s' to '%s' to '%s'", from_str, to_str, file_path)


def _get_db_connection():
    dbname = os.getenv("PGDATABASE", "postgres")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "postgres")
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", 5432)
    return psycopg2.connect(f"dbname={dbname} user={user} password={password} host={host}, port={port}")


def _get_s3():
    aws_key = os.environ.get("REVENUES_AWS_KEY_ID")
    aws_secret = os.environ.get("REVENUES_AWS_SECRET_ACCESS_KEY")

    kwargs = {}
    if aws_key:
        kwargs["aws_access_key_id"] = aws_key
    if aws_secret:
        kwargs["aws_secret_access_key"] = aws_secret

    return boto3.client("s3", **kwargs)

def with_monitoring():
    if os.getenv("DEBUG", None):
        main()
        return
    from telegram.ext import Updater

    private_group = os.environ.get('TG_YFIREBOT_GROUP_INTERNAL')
    public_group = os.environ.get('TG_YFIREBOT_GROUP_EXTERNAL')
    updater = Updater(os.environ.get('TG_YFIREBOT'))
    now = datetime.now()
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