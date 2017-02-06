from slackclient import SlackClient
from config import BOT_TOKEN, BOT_ID
import time
from pm_bibtex import fetch
import re
import logging

AT_BOT = "<@" + BOT_ID + ">"

def process_slack_output(sc, slack_rtm_output):
    for msg in slack_rtm_output:
        print(msg)
        if "type" in msg and msg["type"] == "message" and \
            "user" in msg and msg["user"] != BOT_ID and \
            "text" in msg and AT_BOT in msg["text"]: 
            logging.info("Hey! Someone is talking to me!")
            sc.rtm_send_message(message="Sure, I'm going to find a pdf for that!", channel = msg["channel"])
            links = re.findall("<[^@][^>]+>", msg["text"])
            for l in links:
                l = l[1:-1]
                logging.info("found link: {}".format(l))
                fname, res = fetch(l)
                if fname and res and res[:4] == b'%PDF':
                    logging.info("got pdf: {}".format(fname))
                    res = sc.api_call("files.upload", 
                                      file_type="pdf", 
                                      file_name=fname, 
                                      file=res, 
                                      channels=msg["channel"], 
                                      title=fname, 
                                      initial_comment="<@"+msg["user"]+"> here is your paper!"
                                      )
                else:
                    sc.rtm_send_message(message="... can't find it, sorry <@{}>".format(msg["user"]), channel=msg["channel"])



if __name__ == "__main__":
    sc = SlackClient(BOT_TOKEN)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    READ_DELAY = 1
    if sc.rtm_connect():
        logging.info("paperbot connected to websocket")
        while True:
            process_slack_output(sc, sc.rtm_read())
            time.sleep(READ_DELAY)
    else:
        logging.error("Websocket connection failed")
