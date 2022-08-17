#!/usr/bin/env python3
import json
import logging
import random
import smtplib
import threading
import urllib.request
from email.header import Header
from email.mime.text import MIMEText
from logging import handlers

import sys
import time
import yaml

name = "raingod"


class weather:
    time: str
    date: str
    date_text: str
    whole_wea: str
    week: str
    # day_wea: str
    # night_wea: str
    # whole_temp: str
    day_temp: str
    # night_temp: str


class email:

    def __init__(self, conf):
        self._logger = logging.getLogger()
        self._conf = conf
        try:
            self._pwd = self._conf['pwd']
        except BaseException as e:
            raise Exception("get email pwd err: {}".format(e))

        try:
            self._user = self._conf['user']
        except BaseException as e:
            raise Exception("get email user err: {}".format(e))
        try:
            self._to = str(self._conf['to']).split(",")
        except BaseException as e:
            raise Exception("get email to err: {}".format(e))
        try:
            self._smtp = self._conf['smtp']
        except BaseException as e:
            raise Exception("get email smtp err: {}".format(e))

    def send(self, subject: str, content: str):
        smtp = smtplib.SMTP(self._smtp)
        smtp.login(self._user, self._pwd)
        try:
            message = MIMEText(content, 'plain', 'utf-8')
            message['From'] = Header(name, 'utf-8')
            message['Subject'] = Header(subject, 'utf-8')
            smtp.sendmail(self._user, self._to, message.as_string())
            self._logger.error("send email to {} success".format(self._to))
        except smtplib.SMTPException as e:
            self._logger.error("send email to {} fail: {}".format(self._to, e))
        finally:
            smtp.quit()


class alarm:
    def __init__(self, name: str, email: email):
        self._logger = logging.getLogger()
        self._rain_change = []
        self._tmp_dec_change = []
        self._rain = []
        self._rain_flag = {}
        self._tmp_dec = []
        self._tmp_dec_flag = {}
        self._email = email
        self._name = name

    def try_alarm(self, pre_old_weather: weather, old_weather: weather, pre_new_weather: weather, new_weather: weather):
        if "雨" not in old_weather.whole_wea and "雨" in new_weather.whole_wea:
            self._rain_change.append(
                "{} {}: {} -> {}".format(old_weather.date, old_weather.week, old_weather.whole_wea,
                                         new_weather.whole_wea))
        if "雨" in old_weather.whole_wea and "雨" not in new_weather.whole_wea:
            self._rain_change.append(
                "{} {}: {} -> {}".format(old_weather.date, old_weather.week, old_weather.whole_wea,
                                         new_weather.whole_wea))
        old_min_tmp = pre_old_weather is not None and (int(pre_old_weather.day_temp) - int(old_weather.day_temp)) < 5
        new_max_tmp = pre_new_weather is not None and (int(pre_new_weather.day_temp) - int(new_weather.day_temp)) >= 5
        old_max_tmp = pre_old_weather is not None and (int(pre_old_weather.day_temp) - int(old_weather.day_temp)) >= 5
        new_min_tmp = pre_new_weather is not None and (int(pre_new_weather.day_temp) - int(new_weather.day_temp)) < 5
        if (old_min_tmp and new_max_tmp) or (old_max_tmp and new_min_tmp):
            self._tmp_dec_change.append(
                "{} {}: {} -> {} {}: {} => {} {}: {} -> {} {}: {}".format(pre_old_weather.date, pre_old_weather.week,
                                                                          pre_old_weather.day_temp,
                                                                          old_weather.date, old_weather.week,
                                                                          old_weather.day_temp, pre_new_weather.date,
                                                                          pre_new_weather.week,
                                                                          pre_new_weather.day_temp,
                                                                          new_weather.date, new_weather.week,
                                                                          new_weather.day_temp))

        if new_weather.date_text == "明天":
            flag_key = "{}-{}".format(self._name, new_weather.date)
            pre_flag_key = "{}-{}".format(self._name, pre_new_weather.date)
            if self._tmp_dec_flag.get(flag_key) is None:
                self._tmp_dec_flag[pre_flag_key] = None
                self._tmp_dec_flag[flag_key] = True
                if int(pre_new_weather.day_temp) - int(new_weather.day_temp) > 5:
                    self._tmp_dec.append(
                        "{} {}: {} -> {} {}: {}".format(pre_new_weather.date, pre_new_weather.week,
                                                        pre_new_weather.day_temp, new_weather.date, new_weather.week,
                                                        new_weather.day_temp))

        if new_weather.date_text == "明天":
            flag_key = "{}-{}".format(self._name, new_weather.date)
            pre_flag_key = "{}-{}".format(self._name, pre_new_weather.date)
            if self._rain_flag.get(flag_key) is None:
                self._rain_flag[pre_flag_key] = None
                self._rain_flag[flag_key] = True
                if "雨" in new_weather.whole_wea:
                    self._rain.append(
                        "{} {}: {}".format(new_weather.date, new_weather.week, new_weather.whole_wea))

    def _clear(self):
        self._rain_change = []
        self._tmp_dec_change = []
        self._rain = []
        self._tmp_dec = []

    def do_it(self):
        content = []
        subject = []
        if len(self._tmp_dec) > 0:
            s = "明天气温大降"
            subject.append(s)
            content.append(s + "：\n" + "\n".join(self._tmp_dec))
        if len(self._rain) > 0:
            s = "明天下雨"
            subject.append(s)
            content.append(s + "：\n" + "\n".join(self._rain))
        if len(self._rain_change) > 0:
            s = "天气大幅更新"
            subject.append(s)
            content.append(s + "：\n" + "\n".join(self._rain_change))
        if len(self._tmp_dec_change) > 0:
            s = "气温大幅更新"
            subject.append(s)
            content.append(s + "：\n" + "\n".join(self._tmp_dec_change))
        if len(content) > 0:
            content = "\n".join(content)
            subject = self._name + ": " + ",".join(subject)
            self._logger.info(subject + "\n" + content)
            self._email.send(subject, content)
        self._clear()


class report:
    def __init__(self, conf):
        self._logger = logging.getLogger()
        self._conf = conf
        self._weather_m = {}
        self._email = email(conf['email'])

        try:
            self._url = self._conf["url"]
        except BaseException as e:
            raise Exception("get url err: {}".format(e))
        try:
            self._headers = self._conf["headers"]
        except BaseException as e:
            raise Exception("get headers err: {}".format(e))
        try:
            self._name = self._conf["name"]
        except BaseException as e:
            raise Exception("get name err: {}".format(e))
        self._alarm = alarm(self._name, self._email)
        return

    def name(self) -> str:
        return self._name

    def analyze(self):
        req = urllib.request.Request(self._url, data=None, headers=self._headers)
        resp = urllib.request.urlopen(req)
        resp = json.loads(resp.read())

        self._logger.info("fetch {} resp code: {}".format(self._name, resp['code']))
        self._logger.debug("fetch {} resp: {}".format(self._name, json.dumps(resp, ensure_ascii=False)))
        new_weather_m = {}
        old_weather_m = self._weather_m
        for data in resp['data']:
            weather_d = weather()
            weather_d.time = time.localtime(data['time'])
            weather_d.date = data['date']
            weather_d.whole_wea = data['whole_wea']
            # weather_d.whole_wea = random.sample(["雨", "小雨", "晴天", "大晴天", "阴天"], 1)[0]
            # weather_d.day_wea = data['day_wea']
            # weather_d.night_wea = data['night_wea']
            # weather_d.whole_temp = data['whole_temp']
            weather_d.day_temp = data['day_temp']
            # weather_d.day_temp = random.sample([39, 25, 33, 75], 1)[0]
            # weather_d.night_temp = data['night_temp']
            weather_d.date_text = data['date_text']
            weather_d.week = data['week']
            new_weather_m[weather_d.date] = weather_d
        if len(old_weather_m) != 0:
            pre_new_weather = None
            pre_old_weather = None
            for k in old_weather_m:
                old_weather = old_weather_m[k]
                new_weather = new_weather_m.get(k)
                if new_weather is None:
                    continue
                self._alarm.try_alarm(pre_old_weather, old_weather, pre_new_weather, new_weather)
                pre_new_weather = new_weather
                pre_old_weather = old_weather
            self._alarm.do_it()
        self._weather_m = new_weather_m


class raingod:
    def __init__(self, conf: {}):
        self._logger = logging.getLogger()
        self._conf = conf
        self._reports = []
        try:
            reports = self._conf["reports"]
            for rep in reports:
                self._reports.append(report(rep))
        except BaseException as e:
            raise Exception("get reports err: {}".format(e))

    def __str__(self):
        return str(self._conf)

    def analyze(self, rep: report):
        while 1:
            try:
                rep.analyze()
            except BaseException as e:
                self._logger.info("analyze {} err: {}".format(rep.name(), e))
            sec = random.randint(30, 300)
            # sec = random.randint(1, 5)
            self._logger.info("fetch {} in {}s...".format(rep.name(), sec))
            time.sleep(sec)

    def start(self):
        for rep in self._reports:
            t = threading.Thread(target=self.analyze, args=(rep,))
            t.setDaemon(True)
            t.start()
        while 1:
            time.sleep(1000)


def main():
    if len(sys.argv) != 2:
        config_file = "./{}.yaml".format(name)
    else:
        config_file = sys.argv[1]
    with open(config_file, 'r') as f:
        conf = yaml.safe_load(f)
    lev = logging.INFO
    try:
        debug = conf['debug']
    except BaseException as e:
        debug = False
    if debug:
        lev = logging.DEBUG
    hs = []
    file_handler = handlers.TimedRotatingFileHandler(filename="./{}.log".format(name), when='D', backupCount=1,
                                                     encoding='utf-8')
    hs.append(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    hs.append(console_handler)
    logging.basicConfig(level=lev,
                        format='%(asctime)s %(levelname)s %(pathname)s:%(lineno)d %(thread)s %(message)s', handlers=hs)
    logger = logging.getLogger()
    rm = raingod(conf)
    logger.info("{} info: {}".format(name, rm))
    rm.start()


if __name__ == "__main__":
    main()
