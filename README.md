# chat-karma
A discord bot that utilizes perspective AI to moderate user's chat.

![](https://img.shields.io/pypi/pyversions/nextcord?style=flat-square)
![](https://img.shields.io/github/release-date-pre/SuhJae/chat-karma?style=flat-square)
![](https://img.shields.io/github/license/SuhJae/chat-karma?style=flat-square)

Filtering user chat is a crucial part of moderating a discord server. However, there is some limitation to the current filtering methods. For example, the current filtering methods cannot detect toxic language that is not explicitly stated. For example, the word "pig" is not offensive, but if it is used in a sentence like "You are fat like a pig," it could be considered offensive. This is where chat karma comes in. Chat-karma uses the perspective API to detect toxic behavior in the sentence. This allows the bot to filter toxic language that is not explicitly stated.



## Requirements
* [Python 3.8+](https://www.python.org/downloads/)
* [Redis server](https://redis.io/docs/getting-started/)
* [Perspective API key](https://www.perspectiveapi.com/#/home)

**Python packages**

* [Redis](https://pypi.org/project/redis/) (`pip install redis`)
* [Nextcord](https://pypi.org/project/nextcord/) (`pip install nextcord`)

## Setup
1. Clone the repository.
2. Install the required packages stated above.
3. Put your Discord bot token and token to Perspective Ai in the `config.ini` file.
4. Edit the Redis config.
* If you just installed the Redis client on your computer and did not make any changes, delete `YOUR_PASSWORD_HERE.` and leave it as a blank.
* If you are using an external Redis server, you must edit the host, port, and password accordingly.
  * This is not recommended since this bot takes advantage of the fast speed of the Redis server, and running the database and bot on a separate machine creates network latency.
5. Run main.py
6. Invite the bot to your server.

## Commands
/karma `user`(optional) - Shows the user's karma(Shows how user is positive or negative based on chats that the bot watched).

/dashboard - Opens the dashboard.

/ping - Shows the bot's latency.

/help - Shows the help message.