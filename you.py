#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import requests
import json
import datetime
import shutil

#from apiclient.discovery import build

version = "1.25"
logf = ""
appdir = os.path.dirname(os.path.abspath(__file__))
logfile = appdir + "\\youtube.log"
videoidf = appdir + "\\videoid.txt"
resultf = appdir + "\\result.txt"
resultf_org = appdir + "\\result_org.txt"
conffile = appdir + "\\youtube.conf"
datefile = appdir + "\\date.txt"
dailydata = appdir + "\\dailydata.txt"   # 日々のデータ  形式 yy/mm/dd videoid count  (tab区切り)
dailydata_org = appdir + "\\dailydata_org.txt"   # バックアップ用

token = ""
api_key = ""
base_url = "https://www.googleapis.com/youtube/v3/videos?part=statistics&id={}&fields=items%2Fstatistics&key={}"
idlist = {}
current = {}
prevdate = ""
curdate = ""
dailyf = ""

#  video ID とタイトルの対応表読み込み
def read_videoid() :
    global idlist
    idf = open(videoidf,'r', encoding='utf-8')
    for line in idf :
        line = line.strip()
        id,title,cdate = line.split("\t")
        idlist[id] = title
    idf.close()

#   過去のカウント等のデータ読み込み  
def read_current_count() :
    global current
    items = {}

    countf = open(resultf,'r', encoding='utf-8')
    for line in countf :
       line = line.strip()
       id,count,like,dislike,favorite,comment = line.split("\t")
       items['count'] = int(count)
       items['like'] = int(like)
       items['comment'] = int(comment)
       current[id] = items.copy()

#   前回実行時の日付の読み込み
def read_prevdate() :
    global  prevdate
    if not  os.path.isfile(datefile) :
        prevdate = ""
        return
    f = open(datefile,'r', encoding='utf-8')
    prevdate  = f.readline()
    print(prevdate)

#   現在の値が過去の値よりも増えたら LINE に通知する
def check_count(id,count,like,comment) :
    items = {}

    if not id in current:
        return 0,0
    items = current[id] 
    oldvalue = items['count']
    # count と like は過去を上回ったら表示  (値が下がる場合があるため)
    #print("count {} oldvalue = {} ".format(count, oldvalue))
    newcount = oldvalue 

    if count > oldvalue :
        report("Y {} = {}(+{}) ".format(idlist[id],count,count-oldvalue))  
        newcount = count
    oldvalue = items['like']
    newlike = oldvalue
    if like > oldvalue :
        report("Youtube {} like = {} ".format(idlist[id],like))  
        newlike = like
    oldvalue = items['comment']
    if comment != oldvalue :
        report("Youtube {} comment = {} ".format(idlist[id],comment))  
    return newcount,newlike

def report(mes) :
#    logf.write("report \n")
    line_notify_token = token
    line_notify_api = 'https://notify-api.line.me/api/notify'
    payload = {'message': mes}
    headers = {'Authorization': 'Bearer ' + line_notify_token}  
    line_notify = requests.post(line_notify_api, data=payload, headers=headers)

def main_proc() :
    global token,api_key,curdate,dailyf,logf
    dailydata_flg = 0      #  1 の時、dailydata を出力する
    err = 0                #  1 の時、エラー

    logf = open(logfile,'a', encoding='utf-8')
    logf.write(f'{datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")} start \n' )

    #  設定ファイル読み込み
    conf = open(conffile, 'r', encoding='utf-8')
    api_key  = conf.readline().strip()
    token = conf.readline().strip()
    conf.close()
    
    read_videoid()
    read_current_count()
    read_prevdate()
    shutil.copy(resultf,resultf_org)   
    # if os.path.exists(resultf_org) :
    #     os.remove(resultf_org) 
    # os.rename(resultf, resultf_org)     #  アクセスエラーに備えて結果ファイルバックアップ
    resf = open(resultf,'w', encoding='utf-8')

    curdate = datetime.datetime.now().strftime("%Y/%m/%d")
    #   前回実行時と日付が変わったら dailydata を出力する
    if curdate != prevdate :
        dailydata_flg = 1 
        # if os.path.exists(dailydata_org) :
        #     os.remove(dailydata_org) 
        shutil.copy(dailydata, dailydata_org)     #  アクセスエラーに備えて結果ファイルバックアップ
        dailyf = open(dailydata,'a', encoding='utf-8')

    for id in idlist.keys() :
        url = base_url.format(id,api_key)
        res = json.loads(requests.get(url,verify=False).text)
        count = int(res["items"][0]["statistics"]["viewCount"])
        if count == 0 :     # countが0ならエラーとみなす
            err = 1 
            break 
        like = int(res["items"][0]["statistics"]["likeCount"])
        comment = int(res["items"][0]["statistics"]["commentCount"])
        dislike = 0 
        favorite = 0
        newcount,newlike = check_count(id,count,like,comment)
        resf.write(f"{id}\t{newcount}\t{newlike}\t{dislike}\t{favorite}\t{comment}\n")

        if dailydata_flg == 1 :
            dailyf.write(f"{curdate}\t{id}\t{newcount}\n")

    resf.close()
    if dailydata_flg == 1 :
        dailyf.close()

    if err == 1 :
        logf.write(f'{datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")} *** ERROR count = 0  \n' )
        report("ERROR count=0")
        # if os.path.exists(resultf) :
        #     os.remove(resultf) 
        shutil.copy(resultf_org, resultf)     
        if dailydata_flg == 1 :
            shutil.copy(dailydata_org,dailydata)
        return

    f = open(datefile,'w', encoding='utf-8')
    f.write(curdate)
    f.close()
    logf.write(f'{datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")} end \n' )
    logf.close()

# -------------------------------------------------------------
main_proc()

