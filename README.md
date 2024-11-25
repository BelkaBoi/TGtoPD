# TGtoPD
Telegram bot for ProfitDrive api

# !!! Currently does not work, seems to be a problem on ProfitDrive api side, since it requires ownerid which is not available in both account settings AND using dynamic account data gathering using /auth/login !!!
For the reason above no functionality has been tested for now.

# Info
1. The bot answers to any user messaging /start with "Hello! Your user id is: {userid}. \nSend media to upload!" with "Files" button ({userid} is the telegram userid)
2. After sending media tries to find {userid} folder in the root of the PD account, if not found creates one with the name "{userid}"
3. When "Files" button is pressed tries to find {userid} folder on the root of the account and retrieve files. Lists the files if found and provies "/download?file={fileid}", "/delete?file={fileid} and "/share?file={fileid}" ({fileid} is a madeup number for the file in the specific {userid} directory; Sharing is supposed to create a direct link to the file)


# Usage
1. Enter your telegram token and profitdrive email and password (uses account details instead of api for dynamic api creation as an attempt to gather ownerid from account info if it appears later on)
2. Run TGtoDP.py using python3 >=v20
