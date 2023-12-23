#!/usr/bin/env python3
"""
httprint-console

Copyright 2023 itec <itec@ventuordici.org>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import time
import os
import subprocess
from subprocess import DEVNULL
import logging
import json


import requests
import configparser
import tempfile
import socket

from getkey import getkey, keys

TMP = tempfile.gettempdir()


CODE_DIGITS = 4
temp_digits = 0

PRINT_CMD = "lp -n %(copies)s -o sides=%(sides)s -o media=%(media)s %(colormodel)s -o fit-to-page %(in)s"
PRINTRAW_CMD = "lp -o raw %(in)s"


# Read configuration
config = configparser.ConfigParser()
config.read('console.conf')

confmain = config['MAIN']
DEVICENAME = confmain.get('devicename','')
SERVER = confmain.get('server','')
TOKEN = confmain.get('token','')
# ps = confmain.get('prespool','false')
# PRESPOOL = ps.lower() in ['true', '1', 'y', 'yes']
PRESPOOL = False
INSTANCENAME = "HTTPRINT"
colors = []


def main():
    logfname = os.path.join(os.path.dirname(os.path.realpath(__file__)),"console.log")
    logging.basicConfig(filename=logfname, datefmt='%m/%d/%Y %H:%M:%S', format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
    # logging.getLogger().addHandler(logging.StreamHandler())

    url = f"{SERVER}/api/serverinfo"
    try:
        response = requests.get(url, timeout=5)
    except requests.exceptions.RequestException as e:
        logging.error("Server connection error")
        play("fail")
        display("Error", "No server")
        return()
    
    message = response.json().get("message")
    INSTANCENAME = message.get("instance-name")
    CODE_DIGITS = message.get("code-digits")


    play("start")
    logging.info("start")
    logging.info("DEVICENAME: " + DEVICENAME)
    logging.info("SERVER: " + SERVER)
    # logging.info("PRESPOOL: " + str(PRESPOOL))

    display(INSTANCENAME, DEVICENAME)
    resetdisplay = True
    displaytime = time.time() + 10

    # #search ppd file
    # prn = subprocess.check_output("lpstat -d | awk '{print $NF}'", shell=True).decode("utf-8").strip()
    # logging.info("prn: " + prn)
    # ppd = "/etc/cups/ppd/" + prn +".ppd"
    # logging.info("ppd: " + ppd)
    # #search standard ppd name
    # with open(ppd) as ppdfile:
    #     ppdstd = [x for x in ppdfile if x.startswith("*PCFileName:")]
    #     ppdstd = ppdstd[0].lower().split('"')[1].split(".ppd")[0]
    # logging.info("ppdstd: " + ppdstd)
    
    #search color capabilities
    global colors
    try:
        col = subprocess.check_output("lpoptions -l | grep ColorModel", shell=True).decode("utf-8").strip()
        col = col.split(":")[1]
        col = col.replace("*","").strip().split(" ")
        if len(col) == 1:
            colors = [col[0], col[0]]
        elif len(col) == 2:
            colgray = [i for i in col if i.lower() in ["gray","grayscale"]][0]
            colcol = [i for i in col if i != colgray][0]
            colors = [colgray, colcol]
    except:
        pass


    code = ""
    global key_lookup
    key_lookup = ""
    global temp_digits
    temp_digits = CODE_DIGITS

    #loop
    while True:
        time.sleep(0.05)

        if resetdisplay == True and time.time() > displaytime:
            temp_digits = CODE_DIGITS
            resetdisplay = False
            displaycode(code)

        if code != '':
            if time.time() > keytime + 3:
                code = ''
                #keytime = time.time()
                logging.debug ("Reset")
                play("reset")
                displaycode(code)

        key_lookup = getkey(blocking=False).upper()

        if key_lookup != "":
            # print(key_lookup)
            keytime = time.time()
            if(key_lookup == keys.DELETE):
                code = ''
                temp_digits = CODE_DIGITS
                logging.debug ("Reset")
                play("reset")
                displaycode(code)
            # elif(key_lookup == keys.BACKSPACE): #Used to delete one char
            #     code = code[:-1]
            #     play("button")
            #     displaycode(code)
            elif key_lookup in list("1234567890ABCD*#"):
                code += key_lookup
                play("button")

                if code == "ACA": # ACAB easter egg
                    temp_digits = 4
                if code == "*99": # clean queue, only for service
                    subprocess.call("cancel -a -x", shell=True)
                    code = ''
                    logging.debug ("Queue cleaned")
                    play("print")
                if code == "*98": # show ip, only for service
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("1.1.1.1", 80))
                    display("IP",s.getsockname()[0])
                    play("print")
                    code = ''
                    resetdisplay = True
                    temp_digits = CODE_DIGITS
                    displaytime = time.time() + 5
                else:
                    displaycode(code)

            if len(code) == temp_digits:
                logging.debug(code)
                ppdstd = ""
                searchprint(code, ppdstd, PRESPOOL)

                code = ''
                resetdisplay = True
                temp_digits = CODE_DIGITS
                displaytime = time.time() + 5

            key_lookup = ""



def displaycode(code):
    display("Enter code", formatcode(code))

def display(ro1, ro2):
    r1 = ro1[:16].center(16,' ')
    r2 = ro2[:16].center(16,' ')
    #.write_string(r1 + '\r\n' + r2)
    print(r1 + ' ' + r2, end="\r")

def formatcode(code):
    ccode = code + "_"*(temp_digits - len(code))
    if temp_digits == 6:
        return '-'.join((ccode[:3], ccode[3:]))
    else:
        return(ccode)

def play(file):
    file = os.path.join("sounds", file + ".mp3")
    if os.path.isfile(file):
        subprocess.Popen("mpg123 "+ file, shell=True, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)


def searchprint(code, ppdstd, ps):

    logging.info ("Searching " + code)
    display("Searching...", "")

    url = f"{SERVER}/api/download/{code}?token={TOKEN}"
    if ps:
        url = f"{url}&ppdstd={ppdstd}"

    try:
        response = requests.get(url, timeout=5)
    except requests.exceptions.RequestException as e:
        logging.error("Server connection error")
        play("fail")
        display("Error", "No server")
        return()

    if 'application/json' in response.headers.get('Content-Type', ''):
        jsonResponse = response.json()
        if jsonResponse["error"]:
            logging.error ("Error" + jsonResponse["message"])
            play("fail")
            display("Error", jsonResponse["message"])
            return()

    elif not 'application/octet-stream' in response.headers.get('Content-Type', ''):
        play("fail")
        display("Error", "Bad header")
        return()

    fname = response.headers['Content-Disposition'].split("filename=")[1]
    tfname = os.path.join(TMP, fname)
    with open(tfname, 'wb') as f:
        f.write(response.content)
    printconf = json.loads(response.headers['Printconf'])

    name = printconf.get("name",os.path.splitext(fname.replace(code + "-",""))[0])
    copies = printconf.get("copies", 1)
    sides = printconf.get("sides", "two-sided-long-edge")
    media = printconf.get("media", "A4")
    color = strbool(printconf.get("color", False))

    colormodel = ""
    if colors:
        colormodel = colors[0] if not color else colors[1]
        colormodel = "-o ColorModel=" + colormodel

    logging.info ("Printing " + tfname)
    play("print")
    display("Printing", name)

    #print
    if ps:
        cmd = PRINTRAW_CMD.split(' ')
        cmd = [x % {'in': tfname} for x in cmd]
    else:
        cmd = PRINT_CMD.split(' ')
        cmd = [x % {'in': tfname, 'copies': copies, 'sides': sides, 'media': media, 'colormodel': colormodel} for x in cmd]

    cmd = " ".join(cmd)

    logging.debug(cmd)
    subprocess.call(cmd, shell=True, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
    os.remove(tfname)


def strbool(s):
    return s.lower() in ('true', '1', 't', 'y', 'yes')



if __name__ == "__main__":
    main()
