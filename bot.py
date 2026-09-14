import re
import asyncio
import logging
import aiohttp
import signal
import sys
from datetime import datetime, timedelta
from pyrogram.enums import ParseMode
# @ImposterOnline
from pyrogram import Client, filters, idle
from pyrogram.errors import (
    UserAlreadyParticipant,
    InviteHashExpired,
    InviteHashInvalid,
    PeerIdInvalid,
    ChannelPrivate,
    UsernameNotOccupied,
    FloodWait
)
# @Pirooo_0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
API_ID = "29426930"
API_HASH = "392eb9cd1fd2dd013893521b9ddfc3dc"
BOT_TOKEN = "8945843927:AAGJhZ0pX9Ch7rxeXBqbG4u8Bvjnv9m05lM"
PHONE_NUMBER="+628561319962"
SOURCE_GROUP = -1004481906969
TARGET_CHANNELS = [
    -1003355700495,
]
# @Pirooo_0

user = Client(
    "cc_monitor_user",
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE_NUMBER,
    workers=100
)

bot = Client(
    "cc_monitor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

is_running = True
last_processed_message_id = None
processed_messages = set()
# @Pirooo_0

async def refresh_dialogs(client):
    logger.info("🔄 Refreshing dialogs...")
    dialogs = []
    async for dialog in client.get_dialogs(limit=200):
        dialogs.append(dialog)
    logger.info(f"✅ Refreshed {len(dialogs)} dialogs")
    return True
# @Pirooo_0

async def list_user_groups(client):
    logger.info("🔍 Listing all accessible groups...")
    group_count = 0
    async for dialog in client.get_dialogs():
        if dialog.chat.type in ["group", "supergroup"]:
            logger.info(f"📁 Group: {dialog.chat.title} | ID: {dialog.chat.id}")
            group_count += 1
    logger.info(f"✅ Total accessible groups: {group_count}")
    return True
# @Pirooo_0

async def find_group_by_id(client, target_id):
    async for dialog in client.get_dialogs():
        if dialog.chat.id == target_id:
            logger.info(f"✅ Found target group in dialogs: {dialog.chat.title}")
            return dialog.chat
    return None
# @Pirooo_0

async def ensure_group_access(client, group_id):
    try:
        await refresh_dialogs(client)
        await asyncio.sleep(3)
        found_chat = await find_group_by_id(client, group_id)
        if found_chat:
            logger.info(f"✅ Group found in dialogs: {found_chat.title}")
            return True
# @Pirooo_0
        try:
            chat = await client.get_chat(group_id)
            logger.info(f"✅ Direct access to group: {chat.title}")
            return True
        except (PeerIdInvalid, ChannelPrivate) as e:
            logger.warning(f"⚠️ Direct access failed for group {group_id}: {e}")
            try:
                logger.info("🔄 Attempting to join group...")
                await client.join_chat(group_id)
                logger.info(f"✅ Successfully joined group {group_id}")
                await refresh_dialogs(client)
                await asyncio.sleep(2)
                return True
# @Pirooo_0
            except Exception as join_error:
                logger.error(f"❌ Failed to join group {group_id}: {join_error}")
                return False
    except Exception as e:
        logger.error(f"❌ Error ensuring group access: {e}")
        return False
# @Pirooo_0

async def send_to_target_channels(formatted_message, cc_data):
    for channel_id in TARGET_CHANNELS:
        try:
            await bot.send_message(
                chat_id=channel_id,
                text=formatted_message,
                parse_mode=ParseMode.DEFAULT
            )
            logger.info(f"✅ Sent CC {cc_data[:12]}*** to channel {channel_id}")
            await asyncio.sleep(0.5)
# @Pirooo_0
        except Exception as e:
            logger.error(f"❌ Failed to send CC to channel {channel_id}: {e}")

async def test_access():
    try:
        logger.info("🔍 Debugging: Listing all accessible groups...")
        await list_user_groups(user)
        logger.info(f"Testing access to source group: {SOURCE_GROUP}")
        source_access = await ensure_group_access(user, SOURCE_GROUP)
        if not source_access:
            logger.error(f"❌ Cannot access source group {SOURCE_GROUP}")
            return False
# @Pirooo_0
        for channel_id in TARGET_CHANNELS:
            logger.info(f"Testing access to target channel: {channel_id}")
            try:
                target_chat = await user.get_chat(channel_id)
                logger.info(f"✅ User client can access: {target_chat.title}")
            except Exception as e:
                logger.error(f"❌ Cannot access target channel {channel_id}: {e}")
                return False
        return True
# @Pirooo_0
    except Exception as e:
        logger.error(f"Error in test_access: {e}")
        return False

async def get_bin_info(bin_number):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{bin_number}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"BIN API returned status {response.status} for BIN {bin_number}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching BIN info for {bin_number}: {e}")
        return None
# @Pirooo_0

def extract_credit_cards(text):
    if not text:
        return []
    patterns = [
        r'\b(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})\b',
        r'\b(\d{13,19})\s*\|\s*(\d{1,2})\s*\|\s*(\d{2,4})\s*\|\s*(\d{3,4})\b',
        r'\b(\d{13,19})\D+(\d{1,2})\D+(\d{2,4})\D+(\d{3,4})\b',
        r'(\d{13,19})\s*[\|\/\-:\s]\s*(\d{1,2})\s*[\|\/\-:\s]\s*(\d{2,4})\s*[\|\/\-:\s]\s*(\d{3,4})',
        r'(\d{4})\s*(\d{4})\s*(\d{4})\s*(\d{4})\s*[\|\/\-:\s]\s*(\d{1,2})\s*[\|\/\-:\s]\s*(\d{2,4})\s*[\|\/\-:\s]\s*(\d{3,4})',
    ]
    credit_cards = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) == 4:
                card_number, month, year, cvv = match
                card_number = re.sub(r'[\s\-]', '', card_number)
# @ImposterOnline
            elif len(match) == 7:
                card1, card2, card3, card4, month, year, cvv = match
                card_number = card1 + card2 + card3 + card4
            else:
                continue
            if len(card_number) < 13 or len(card_number) > 19:
                continue
            try:
                month_int = int(month)
                if not (1 <= month_int <= 12):
                    continue
            except ValueError:
                continue
# @ImposterOnline
            if len(year) == 4:
                year = year[-2:]
            elif len(year) != 2:
                continue
            if len(cvv) < 3 or len(cvv) > 4:
                continue
            credit_cards.append(f"{card_number}|{month.zfill(2)}|{year}|{cvv}")
    seen = set()
    unique_cards = []
    for card in credit_cards:
        if card not in seen:
            seen.add(card)
            unique_cards.append(card)
# @ImposterOnline
    return unique_cards

def format_card_message(cc_data, bin_info):
    scheme = "UNKNOWN"
    card_type = "UNKNOWN"
    brand = "UNKNOWN"
    bank_name = "UNKNOWN BANK"
    country_name = "UNKNOWN"
    country_emoji = "🌍"
    if bin_info:
        brand = bin_info.get('brand', 'UNKNOWN')
        scheme = brand
# @ImposterOnline
        card_type = bin_info.get('type', 'UNKNOWN').upper()
        bank_name = bin_info.get('bank', 'UNKNOWN BANK')
        country_name = bin_info.get('country_name', 'UNKNOWN')
        country_emoji = bin_info.get('country_flag', '🌍')
    message = f"""[ϟ] ʙɪᴛᴄʜ ꜱᴄʀᴀᴘᴘᴇʀ [ϟ]

𝗦𝘁𝗮𝘁𝘂𝘀 - Approved ✅
━━━━━━━━━━━━━
[ϟ] 𝗖𝗖 ⌁ <code>{cc_data}</code>
[ϟ] 𝗦𝘁𝗮𝘁𝘂𝘀 : Payment method added successfully ✅
[ϟ] 𝗚𝗮𝘁𝗲 - Stripe Auth 
━━━━━━━━━━━━━
[ϟ] 𝗖𝗼𝘂𝗻𝘁𝗿𝘆 : <code>{country_name} {country_emoji}</code>
[ϟ] 𝗜𝘀𝘀𝘂𝗲𝗿 : <code>{bank_name}</code>
[ϟ] 𝗧𝘆𝗽𝗲 : <code>{card_type} - {brand}</code>
━━━━━━━━━━━━━
[ϟ] <b>Proxy : Live ⚡</b>
[ϟ] 𝗦𝗰𝗿𝗮𝗽𝗽𝗲𝗱 𝗕𝘆 : @Pirooo_0
    """
    return message
# @ImposterOnline

async def process_message_for_ccs(message):
    global processed_messages
    try:
        if message.id in processed_messages:
            return
        processed_messages.add(message.id)
        if len(processed_messages) > 1000:
            processed_messages = set(list(processed_messages)[-500:])
# @ImposterOnline
        text = message.text or message.caption
        if not text:
            return
        logger.info(f"📝 Processing message {message.id}: {text[:50]}...")
        credit_cards = extract_credit_cards(text)
        if not credit_cards:
            return
# @ImposterOnline
        logger.info(f"🎯 Found {len(credit_cards)} credit cards in message {message.id}")
        for cc_data in credit_cards:
            try:
                logger.info(f"🔄 Processing CC: {cc_data[:12]}***")
                bin_number = cc_data.split('|')[0][:6]
                bin_info = await get_bin_info(bin_number)
                formatted_message = format_card_message(cc_data, bin_info)
# @ImposterOnline
                await send_to_target_channels(formatted_message, cc_data)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Error processing CC {cc_data}: {e}")
    except Exception as e:
        logger.error(f"❌ Error processing message {message.id}: {e}")
# @ImposterOnline

async def poll_for_new_messages():
    global last_processed_message_id, is_running
    logger.info("🔄 Starting message polling...")
    try:
        async for message in user.get_chat_history(SOURCE_GROUP, limit=1):
            last_processed_message_id = message.id
            logger.info(f"📍 Starting from message ID: {last_processed_message_id}")
            break
    except Exception as e:
        logger.error(f"❌ Error getting initial message ID: {e}")
        return
# @ImposterOnline
    while is_running:
        try:
            logger.info(f"🔍 Polling for new messages after ID {last_processed_message_id}...")
            new_messages = []
            message_count = 0
            async for message in user.get_chat_history(SOURCE_GROUP, limit=50):
                message_count += 1
                if message.id <= last_processed_message_id:
                    break
                new_messages.append(message)
# @ImposterOnline
            new_messages.reverse()
            if new_messages:
                logger.info(f"📨 Found {len(new_messages)} new messages to process")
                for message in new_messages:
                    await process_message_for_ccs(message)
                    last_processed_message_id = max(last_processed_message_id, message.id)
                    await asyncio.sleep(0.5)
            else:
                logger.info(f"📭 No new messages found (checked {message_count} messages)")
# @ImposterOnline
            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"❌ Error in polling loop: {e}")
            await asyncio.sleep(30)
# @ImposterOnline

@user.on_message(filters.chat(SOURCE_GROUP))
async def realtime_message_handler(client, message):
    logger.info(f"🔄 Real-time message received: {message.id}")
    await process_message_for_ccs(message)
# @ImposterOnline

async def test_message_reception():
    try:
        logger.info("🔍 Testing message reception by checking recent history...")
        messages = []
        async for message in user.get_chat_history(SOURCE_GROUP, limit=10):
            messages.append(message)
        logger.info(f"✅ Retrieved {len(messages)} recent messages from source group")
        if messages:
            logger.info("📝 Recent messages preview:")
            for i, msg in enumerate(messages[:3]):
                text = msg.text or msg.caption or "No text"
                logger.info(f"  {i+1}. ID: {msg.id} | Text: {text[:50]}...")
# @ImposterOnline
                if text != "No text":
                    ccs = extract_credit_cards(text)
                    if ccs:
                        logger.info(f"    🎯 Found CC in recent message: {ccs[0][:12]}***")
        return len(messages) > 0
    except Exception as e:
        logger.error(f"❌ Error testing message reception: {e}")
        return False
# @ImposterOnline

async def send_test_message():
    try:
        test_cc = "4532123456789012|12|25|123"
        logger.info(f"🧪 Testing with sample CC: {test_cc}")
        ccs = extract_credit_cards(test_cc)
        if ccs:
            logger.info(f"✅ CC extraction working: {ccs[0]}")
            bin_info = await get_bin_info(ccs[0][:6])
            formatted_message = format_card_message(ccs[0], bin_info)
            logger.info("✅ CC formatting working")
        return True
# @ImposterOnline
    except Exception as e:
        logger.error(f"❌ Error in test: {e}")
        return False

async def force_sync_group():
    try:
        logger.info("🔄 Force syncing with source group...")
        chat = await user.get_chat(SOURCE_GROUP)
        logger.info(f"✅ Group info: {chat.title} ({chat.members_count} members)")
        count = 0
        async for message in user.get_chat_history(SOURCE_GROUP, limit=5):
            count += 1
# @ImposterOnline
        logger.info(f"✅ Read {count} recent messages for sync")
        try:
            await user.read_chat_history(SOURCE_GROUP)
            logger.info("✅ Marked chat as read")
        except Exception as e:
            logger.warning(f"⚠️ Could not mark as read: {e}")
        return True
    except Exception as e:
        logger.error(f"❌ Error syncing group: {e}")
        return False
# @ImposterOnline

def signal_handler(signum, frame):
    global is_running
    logger.info(f"Received signal {signum}, shutting down...")
    is_running = False
# @ImposterOnline

async def main():
    global is_running
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    try:
        logger.info("Starting user client...")
        await user.start()
        await bot.start()
        logger.info("User client started successfully")
        await asyncio.sleep(3)
        logger.info(f"🤖 CC Monitor is now active!")
        logger.info(f"📡 Monitoring group: {SOURCE_GROUP}")
        logger.info(f"📤 Target channels: {TARGET_CHANNELS}")
        logger.info("⏳ Waiting for client to sync...")
# @ImposterOnline
        await asyncio.sleep(5)
        logger.info("Testing access to groups and channels...")
        access_ok = await test_access()
        if not access_ok:
            logger.error("❌ Access test failed! Monitor will continue running but may not work properly.")
        else:
            logger.info("✅ All access tests passed!")
        logger.info("🔄 Force syncing with source group...")
        await force_sync_group()
# @ImposterOnline
        logger.info("🧪 Testing message reception...")
        reception_ok = await test_message_reception()
        if not reception_ok:
            logger.warning("⚠️ Message reception test failed!")
        else:
            logger.info("✅ Message reception test passed!")
        logger.info("🧪 Testing CC processing...")
        await send_test_message()
# @ImposterOnline
        logger.info("🚀 Starting message polling task...")
        polling_task = asyncio.create_task(poll_for_new_messages())
        try:
            logger.info("Monitor is now active and polling for messages every 10 seconds...")
            logger.info("💡 The bot will now actively check for new CCs in the group!")
            await idle()
        finally:
            polling_task.cancel()
            try:
                await polling_task
# @ImposterOnline
            except asyncio.CancelledError:
                pass
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        logger.info("Stopping client...")
        try:
            if user.is_connected:
                await user.stop()
                logger.info("User client stopped")
        except Exception as e:
            logger.error(f"Error stopping client: {e}")
# @ImposterOnline

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
