import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = 'tg bot token'
API_EMAIL = 'profitdrive email'     # Your ProfitDrive account email
API_PASSWORD = 'profitdrive password'  # Your ProfitDrive account password
API_BASE_URL = 'https://pd.heracle.net/api/v1'

# Global variables to store access token and user ID
API_ACCESS_TOKEN = None
USER_ID = None

def authenticate():
    global API_ACCESS_TOKEN, USER_ID
    data = {
        'email': API_EMAIL,
        'password': API_PASSWORD,
        'token_name': 'TelegramBot'  # Changed from 'device_name' to 'token_name'
    }
    response = requests.post(f"{API_BASE_URL}/auth/login", json=data)
    if response.status_code == 200:
        try:
            result = response.json()
            API_ACCESS_TOKEN = result['user']['access_token']
            USER_ID = result['user']['id']
            logger.info("Authentication successful.")
        except Exception as e:
            logger.error(f"Error parsing authentication response: {e}")
            logger.error(f"Response content: {response.text}")
            raise Exception("Failed to authenticate with the API.")
    else:
        logger.error(f"Authentication failed: {response.status_code}, {response.text}")
        raise Exception("Failed to authenticate with the API.")

def get_user_folder_id(user_id):
    headers = {'Authorization': f'Bearer {API_ACCESS_TOKEN}'}
    params = {'query': str(user_id), 'type': 'folder'}
    response = requests.get(f"{API_BASE_URL}/drive/file-entries", params=params, headers=headers)

    if response.status_code == 200:
        try:
            entries = response.json()
            if isinstance(entries, dict) and 'data' in entries:
                entries = entries['data']
            for entry in entries:
                if entry['name'] == str(user_id):
                    return entry['id']
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            logger.error(f"Response content: {response.text}")
    else:
        logger.error(f"Failed to get file entries: {response.status_code}, {response.text}")

    # Folder not found, create it
    data = {'name': str(user_id), 'parentId': None}
    response = requests.post(f"{API_BASE_URL}/folders", json=data, headers=headers)
    if response.status_code == 200:
        try:
            folder = response.json().get('folder')
            if folder:
                return folder['id']
            else:
                logger.error(f"No 'folder' key in response: {response.json()}")
                return None
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            logger.error(f"Response content: {response.text}")
            return None
    else:
        logger.error(f"Failed to create folder: {response.status_code}, {response.text}")
        return None

async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    keyboard = [[InlineKeyboardButton("Files", callback_data='files')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Hello! Your user id is: {user_id}.\nSend media to upload!", reply_markup=reply_markup)

async def handle_media(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    file = None
    if update.message.document:
        file = await update.message.document.get_file()
        file_name = update.message.document.file_name
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()
        file_name = 'photo.jpg'
    elif update.message.video:
        file = await update.message.video.get_file()
        file_name = update.message.video.file_name or 'video.mp4'
    elif update.message.audio:
        file = await update.message.audio.get_file()
        file_name = update.message.audio.file_name or 'audio.mp3'
    elif update.message.voice:
        file = await update.message.voice.get_file()
        file_name = 'voice.ogg'
    else:
        await update.message.reply_text("Please send a valid media or file.")
        return

    file_path = f"{file.file_unique_id}_{file_name}"
    await file.download_to_drive(file_path)

    # Get or create user's folder
    folder_id = get_user_folder_id(user_id)
    if folder_id is None:
        await update.message.reply_text("Failed to create user folder.")
        logger.error(f"Failed to get or create folder for user {user_id}")
        os.remove(file_path)
        return

    files = {'file': open(file_path, 'rb')}
    headers = {'Authorization': f'Bearer {API_ACCESS_TOKEN}'}
    data = {'parentId': folder_id, 'relativePath': file_name}
    response = requests.post(f"{API_BASE_URL}/uploads", files=files, data=data, headers=headers)

    os.remove(file_path)

    if response.status_code == 201:
        await update.message.reply_text("File uploaded successfully!")
    else:
        await update.message.reply_text("Failed to upload the file.")
        logger.error(f"Upload failed: {response.status_code}, {response.text}")

async def files_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    headers = {'Authorization': f'Bearer {API_ACCESS_TOKEN}'}
    folder_id = get_user_folder_id(user_id)
    if folder_id is None:
        await update.message.reply_text("Failed to retrieve your files.")
        logger.error(f"Failed to get folder ID for user {user_id}")
        return
    params = {'parentIds[]': folder_id}
    response = requests.get(f"{API_BASE_URL}/drive/file-entries", params=params, headers=headers)

    if response.status_code == 200:
        try:
            files_list = response.json()
            if isinstance(files_list, dict) and 'data' in files_list:
                files_list = files_list['data']
            if not files_list:
                await update.message.reply_text("You have no files.")
                return

            message = ""
            idx = 1
            for file_info in files_list:
                if file_info['type'] == 'folder':
                    continue
                file_id = file_info['id']
                file_name = file_info['name']
                file_size = file_info['file_size']
                message += f"{idx} | {file_name} | Size: {file_size} bytes | /download?file={file_id} ; /delete?file={file_id}\n"
                idx += 1
            if message:
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("You have no files.")
        except Exception as e:
            await update.message.reply_text("Failed to parse files list.")
            logger.error(f"Error parsing files list: {e}")
            logger.error(f"Response content: {response.text}")
    else:
        await update.message.reply_text("Failed to retrieve files.")
        logger.error(f"List files failed: {response.status_code}, {response.text}")

async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == 'files':
        user_id = query.from_user.id
        headers = {'Authorization': f'Bearer {API_ACCESS_TOKEN}'}
        folder_id = get_user_folder_id(user_id)
        if folder_id is None:
            await query.edit_message_text(text="Failed to retrieve your files.")
            logger.error(f"Failed to get folder ID for user {user_id}")
            return
        params = {'parentIds[]': folder_id}
        response = requests.get(f"{API_BASE_URL}/drive/file-entries", params=params, headers=headers)

        if response.status_code == 200:
            try:
                files_list = response.json()
                if isinstance(files_list, dict) and 'data' in files_list:
                    files_list = files_list['data']
                if not files_list:
                    await query.edit_message_text(text="You have no files.")
                    return

                message = ""
                idx = 1
                for file_info in files_list:
                    if file_info['type'] == 'folder':
                        continue
                    file_id = file_info['id']
                    file_name = file_info['name']
                    file_size = file_info['file_size']
                    message += f"{idx} | {file_name} | Size: {file_size} bytes | /download?file={file_id} ; /delete?file={file_id}\n"
                    idx += 1
                if message:
                    await query.edit_message_text(text=message)
                else:
                    await query.edit_message_text(text="You have no files.")
            except Exception as e:
                await query.edit_message_text(text="Failed to parse files list.")
                logger.error(f"Error parsing files list: {e}")
                logger.error(f"Response content: {response.text}")
        else:
            await query.edit_message_text(text="Failed to retrieve files.")
            logger.error(f"List files failed: {response.status_code}, {response.text}")

async def handle_commands(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.effective_user.id
    headers = {'Authorization': f'Bearer {API_ACCESS_TOKEN}'}

    if text.startswith('/download?file='):
        file_id = text.replace('/download?file=', '').strip()
        folder_id = get_user_folder_id(user_id)
        if folder_id is None:
            await update.message.reply_text("Failed to retrieve your files.")
            logger.error(f"Failed to get folder ID for user {user_id}")
            return
        # Get file details
        params = {'parentIds[]': folder_id}
        response = requests.get(f"{API_BASE_URL}/drive/file-entries", params=params, headers=headers)
        if response.status_code == 200:
            try:
                entries = response.json()
                if isinstance(entries, dict) and 'data' in entries:
                    entries = entries['data']
                file_entry = next((item for item in entries if str(item['id']) == file_id), None)
                if file_entry:
                    # Proceed to download
                    download_url = f"{API_BASE_URL}/file-entries/{file_id}/download"
                    download_response = requests.get(download_url, headers=headers, stream=True)
                    if download_response.status_code == 200:
                        file_name = file_entry['name']
                        with open(file_name, 'wb') as f:
                            for chunk in download_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        await update.message.reply_document(document=open(file_name, 'rb'))
                        os.remove(file_name)
                        # Delete file from server
                        data = {"entryIds": [file_id], "deleteForever": True}
                        delete_response = requests.delete(f"{API_BASE_URL}/file-entries", json=data, headers=headers)
                        if delete_response.status_code == 200:
                            await update.message.reply_text("File downloaded and deleted from the server.")
                        else:
                            await update.message.reply_text("File downloaded but failed to delete from the server.")
                            logger.error(f"Delete failed: {delete_response.status_code}, {delete_response.text}")
                    else:
                        await update.message.reply_text("Failed to download the file.")
                        logger.error(f"Download failed: {download_response.status_code}, {download_response.text}")
                else:
                    await update.message.reply_text("File not found or access denied.")
            except Exception as e:
                await update.message.reply_text("Failed to process your request.")
                logger.error(f"Error processing download: {e}")
                logger.error(f"Response content: {response.text}")
        else:
            await update.message.reply_text("Failed to retrieve file information.")
            logger.error(f"File info failed: {response.status_code}, {response.text}")

    elif text.startswith('/delete?file='):
        file_id = text.replace('/delete?file=', '').strip()
        folder_id = get_user_folder_id(user_id)
        if folder_id is None:
            await update.message.reply_text("Failed to retrieve your files.")
            logger.error(f"Failed to get folder ID for user {user_id}")
            return
        # Get file details
        params = {'parentIds[]': folder_id}
        response = requests.get(f"{API_BASE_URL}/drive/file-entries", params=params, headers=headers)
        if response.status_code == 200:
            try:
                entries = response.json()
                if isinstance(entries, dict) and 'data' in entries:
                    entries = entries['data']
                file_entry = next((item for item in entries if str(item['id']) == file_id), None)
                if file_entry:
                    # Proceed to delete
                    data = {"entryIds": [file_id], "deleteForever": True}
                    response = requests.delete(f"{API_BASE_URL}/file-entries", json=data, headers=headers)
                    if response.status_code == 200:
                        await update.message.reply_text("File deleted successfully.")
                    else:
                        await update.message.reply_text("Failed to delete the file.")
                        logger.error(f"Delete failed: {response.status_code}, {response.text}")
                else:
                    await update.message.reply_text("File not found or access denied.")
            except Exception as e:
                await update.message.reply_text("Failed to process your request.")
                logger.error(f"Error processing delete: {e}")
                logger.error(f"Response content: {response.text}")
        else:
            await update.message.reply_text("Failed to retrieve file information.")
            logger.error(f"File info failed: {response.status_code}, {response.text}")

    else:
        await update.message.reply_text("Unknown command.")

async def error_handler(update: object, context: CallbackContext):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and isinstance(update, Update):
        await update.message.reply_text("An error occurred while processing your request.")

def main():
    authenticate()  # Authenticate and obtain API_ACCESS_TOKEN and USER_ID

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('files', files_command))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE,
        handle_media
    ))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_commands))
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
