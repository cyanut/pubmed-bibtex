from slackclient import SlackClient
import random
rand = random.SystemRandom()
from config import BOT_TOKEN, BOT_ID, AUTHOR_ID, AUTHOR_DM, RAMBLE_LIB, RAMBLE_PROB, RAMBLE_PERIOD
import time
from pm_bibtex import fetch
import re
import logging
import time
import re

AT_BOT = "<@" + BOT_ID + ">"

ramble_dic = {}

def ramble(ramble_lib, msg):
    temp_res = []    
    for (k,v) in ramble_lib:
        if re.search(k, msg["text"]):
            if isinstance(v, str):
                temp_res.append(v)
            elif isinstance(v, type(lambda x:x)):
                temp_res.append(v(msg))
    idx = rand.randint(0, len(temp_res)-1)
    return temp_res[idx]

def process_slack_output(sc, slack_rtm_output):
    for msg in slack_rtm_output:
        if "type" in msg and msg["type"] == "message" and \
            "user" in msg and msg["user"] != BOT_ID and \
            "text" in msg and \
            (AT_BOT in msg["text"] or msg["channel"][0] == "D"): 
            logging.info("Hey! Someone is talking to me!")
            links = re.findall("<[^@][^>]+>", msg["text"])
            if len(links) == 0:
                if (not msg["user"] in ramble_dic or \
                    time.time() - ramble_dic[msg["user"]] > RAMBLE_PERIOD)\
                    and rand.random() < RAMBLE_PROB:
                    ramble_msg = ramble(RAMBLE_LIB, msg)
                    sc.rtm_send_message(message = ramble_msg, channel = msg["channel"])
                    sc.rtm_send_message(message="<@{}> sent this: '{}'. I replied: {}".format(msg["user"], msg["text"], ramble_msg), channel=AUTHOR_DM)
                    ramble_dic[msg["user"]] = time.time()
                continue
                
            sc.rtm_send_message(message="Sure, I'm going to find a pdf for that!", channel = msg["channel"])
            for l in links:
                l = l[1:-1]
                logging.info("found link: {}".format(l))
                try:
                    fname, res = fetch(l)
                except:
                    sc.rtm_send_message(message="... weird, it didn't work. <@{}> must have broken something.".format(AUTHOR_ID), channel=msg["channel"])
                    sc.rtm_send_message(message="<@{}> sent this: '{}', but it didn't work.".format(msg["user"], msg["text"]), channel=AUTHOR_DM)
                    return
                if fname and res and res[:4] == b'%PDF':
                    logging.info("got pdf: {}".format(fname))
                    res = sc.api_call("files.upload", 
                                      filetype="pdf", 
                                      filename=fname, 
                                      file=res, 
                                      channels=msg["channel"], 
                                      title=fname, 
                                      initial_comment="<@"+msg["user"]+"> here is your paper!"
                                      )
                else:
                    sc.rtm_send_message(message="... can't find it, sorry <@{}>, I'm letting <@{}> know.".format(msg["user"], AUTHOR_ID), channel=msg["channel"])
                    sc.rtm_send_message(message="<@{}> sent this: '{}', but it didn't work.".format(msg["user"], msg["text"]), channel=AUTHOR_DM)





if __name__ == "__main__":
    sc = SlackClient(BOT_TOKEN)
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)
    READ_DELAY = 1
    if sc.rtm_connect():
        logging.info("paperbot connected to websocket")
        while True:
            process_slack_output(sc, sc.rtm_read())
            time.sleep(READ_DELAY)
    else:
        logging.error("Websocket connection failed")
