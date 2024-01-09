#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import datetime
import pandas as pd
import requests
from datetime import date,timedelta
from ftplib import FTP_TLS
from datetime import datetime as dt

version = "1.22"   #  24/01/04

debug = 0
logf = ""
appdir = os.path.dirname(os.path.abspath(__file__))
logfile = appdir + "\\youtube.log"
videoidf = appdir + "\\videoid.txt"
conffile = appdir + "\\youtube2.conf"
dailydata = appdir + "\\dailydata.txt"   # 日々のデータ  形式 yy/mm/dd videoid count  (tab区切り)
templatefile = appdir + "./template.htm"
resultfile = appdir + "./youtube.htm"
goodfile = appdir + "./result.txt"    # good の件数取得
prev_goodfile = appdir + "./prevgood.txt"    # 前回のgood件数 
csvfile = appdir + "./replay.csv" 

idlist = {}       # キー videoid  値  タイトル
cdatelist = {}    # キー videoid  値  動画登録日
gooddata = {}     # キー videoid  値  good の件数  
prev_gooddata = {} # キー videoid  値  good の件数  
current = {}
prevdate = ""
curdate = ""
dailyf = ""
df = ""
df_movav = ""
lastdate = ""      # 最終日付
out = ""           # html出力ファイル
video_info = {}    # キー  vid : 値  (キー 現再生回数 , キー 前日再生回数)
daily_info = {}    # 日別再生回数  キー  日付  値  再生回数
monthly_info = {}  # 月別再生回数  キー  yymm 値  総再生回数
mon_data = {}      # 今月のデータ(ランキング用)  キー  日付  値  再生回数  
ftp_host = ftp_user = ftp_pass = ftp_url =  ""
pixela_url = ""
pixela_token = ""

def main_proc() :
    read_config()
    read_videoid()
    read_dailydata()
    read_good_data()
    create_repcount_info()    
    create_daily_info()
    month_count()   
    parse_template()
    ftp_upload()
    post_pixela()

#  video ID とタイトルの対応表読み込み
def read_videoid() :
    global idlist,cdatelist
    idf = open(videoidf,'r', encoding='utf-8')
    for line in idf :
        line = line.strip()
        id,title,cdate = line.split("\t")
        idlist[id] = title
        cdatelist[id] = cdate
    idf.close()

def read_dailydata() :
    global df , lastdate
    df = pd.read_table(dailydata, names=('date', 'vid', 'replay'),parse_dates=[0])
    lastdate = df.iloc[-1]['date']

def read_good_data():
    global gooddata,prev_gooddata
    gf = open(goodfile,'r', encoding='utf-8')
    for line in gf :
        line = line.strip()
        id,_,good,_,_,_ = line.split("\t")
        gooddata[id] = good
    gf.close()
    if os.path.isfile(prev_goodfile) :
        prevf = open(prev_goodfile,'r', encoding='utf-8')
        for line in prevf :
            line = line.strip()
            id,good = line.split("\t")
            prev_gooddata[id] = good
        prevf.close()

    prevf = open(prev_goodfile,'w', encoding='utf-8')
    for id,good  in gooddata.items()  :
        prevf.write(f'{id}\t{good}\n')
    prevf.close()

#   再生回数情報 rep_info を作成する
#   rep_info 辞書  キー  vid  値  video_info 
#       video_info  辞書  キー  all,day,week,mon,mon3  全期間、1日、1週間、1ヶ月、3ヶ月の再生回数  
def create_repcount_info() :
    global rep_info
    priod_list = [1,7,30,90]     #  調査する期間
    priod_key = ["day","week","mon","mon3"]     #  

    today_df = df[df['date'] == lastdate]
    today_rep_tmp = {}
    for _,row in today_df.iterrows() :
        today_rep_tmp[row.vid] = row.replay

    today_rep = {}    #  キー  vid  値   当日までの全再生回数     再生回数順にソート
    today_rep = sorted(today_rep_tmp.items(), key=lambda x:x[1],reverse=True)
    today_rep = dict((x, y) for x, y in today_rep)

    prev_repcnt = []     #  n日前の再生回数の情報   各要素は prev_rep キー vid  値  再生回数
    # prev_repcnt はリスト  1,7,30,90 日前の再生回数の情報が入る
    for priod in priod_list :
        prev_day = lastdate - timedelta(priod)
        prev_df = df[df['date'] == prev_day]
        prev_rep = {}     #  キー  vid  値   priod前の再生回数   
        for _,row in prev_df.iterrows() :
            prev_rep[row.vid] = row.replay
        prev_repcnt.append(prev_rep)

    #  総再生回数 から各期間の再生回数を引くことでその期間の再生回数を求める
    rep_info = {}
    for vid , allrep in today_rep.items() :
        video_info = {}
        video_info['all'] = allrep    #  総再生回数
        
        for prev_rep,key in zip(prev_repcnt,priod_key) :
            if vid in prev_rep :
                video_info[key] = allrep - prev_rep[vid]
            else :
                video_info[key] = allrep
        rep_info[vid] = video_info

    print(rep_info)
    #output_replay_count2()

# 再生回数情報 rep_info を参照し各期間の再生回数を出力する
def output_replay_count2() :
    csvout = open(csvfile,'w' ,  encoding='utf-8')
    csvout.write('タイトル,日,週,月,四半期,全期,投稿日,Good\n')
    for vid,video_info in rep_info.items() :
        title = idlist[vid]
        cdatestr = cdatelist[vid]
        cdate = dt.strptime(cdatestr, '%y/%m/%d')
        alldays = lastdate - cdate      
        fromdays = alldays.days + 1  #  登録日からの日数 初日を 1 とするため +1 する
        
        weekdays = 7
        monthdays = 30
        month3days = 90
        if fromdays < weekdays :
            weekdays = fromdays
        if fromdays < monthdays :
            monthdays = fromdays
        if fromdays < month3days :
            month3days = fromdays
        good_cnt = int(gooddata[vid])
        if vid in prev_gooddata :
            prev_good_cnt = int(prev_gooddata[vid])
            diff_good = good_cnt - prev_good_cnt
        else :
            diff_good = good_cnt

        out.write(f'<tr><td>{title}</td>'
                  f'<td align="right">{video_info["day"]}</td>'
                  f'<td align="right">{video_info["week"]}</td><td align="right">{video_info["week"]/weekdays:.2f}</td>'
                  f'<td align="right">{video_info["mon"]}</td><td align="right">{video_info["mon"]/monthdays:.2f}</td>'
                  f'<td align="right">{video_info["mon3"]}</td><td align="right">{video_info["mon3"]/month3days:.2f}</td>' 
                  f'<td align="right">{video_info["all"]}</td><td align="right">{video_info["all"]/fromdays:.2f}</td>'
                  f'<td align="right">{cdatestr}</td>'
                  f'<td align="right">{good_cnt}</td>'
                  f'<td align="right">{diff_good}</td></tr>\n')
        #csvout.write(f'{title},{up},{weekup},{monup},{mon3up},{count},{cdatestr},{good_cnt}\n')

    csvout.close()

#   未使用
#   video_info を作成する。  
#   video_info は辞書  キー vid  値  repinfo
#   repinfo は辞書  キー   prev_rep,week_rep,mon_rep,mon3_rep,replay  値 前日、週、月、。。までの再生回数             
def today_stat() :
    global video_info

    previous_day = lastdate - timedelta(1)
    previous_week = lastdate - timedelta(7)
    previous_month = lastdate - timedelta(30)  
    previous_month3 = lastdate - timedelta(90)   

    today_df = df[df['date'] == lastdate]
    today_rep_tmp = {}
    for index,row in today_df.iterrows() :
        today_rep_tmp[row.vid] = row.replay

    today_rep = {}    #  キー  vid  値   当日までの再生回数   
    today_rep = sorted(today_rep_tmp.items(), key=lambda x:x[1],reverse=True)
    today_rep = dict((x, y) for x, y in today_rep)
    
    prevday_df = df[df['date'] == previous_day]
    prev_rep = {}     #  キー  vid  値   前日までの再生回数   
    for index,row in prevday_df.iterrows() :
        prev_rep[row.vid] = row.replay

    week_df = df[df['date'] == previous_week]
    week_rep = {}
    for index,row in week_df.iterrows() :
        week_rep[row.vid] = row.replay

    mon_df = df[df['date'] == previous_month]
    mon_rep = {}
    for index,row in mon_df.iterrows() :
        mon_rep[row.vid] = row.replay

    mon3_df = df[df['date'] == previous_month3]
    mon3_rep = {}
    for index,row in mon3_df.iterrows() :
        mon3_rep[row.vid] = row.replay

    for vid , rep in today_rep.items() :
        repinfo = {}
        repinfo['replay'] = rep
        if vid in prev_rep :
            repinfo['prev_rep'] = prev_rep[vid]
        else :
            repinfo['prev_rep'] = 0
        if vid in week_rep :
            repinfo['week_rep'] = week_rep[vid]
        else :
            repinfo['week_rep'] = 0
        if vid in mon_rep :
            repinfo['mon_rep'] = mon_rep[vid]
        else :
            repinfo['mon_rep'] = 0
        if vid in mon3_rep :
            repinfo['mon3_rep'] = mon3_rep[vid]
        else :
            repinfo['mon3_rep'] = 0
        video_info[vid] = repinfo
    
    output_replay_count()

#   未使用
def output_replay_count() :
    csvout = open(csvfile,'w' ,  encoding='utf-8')
    csvout.write('タイトル,日,週,月,四半期,全期,投稿日,Good\n')
    for vid,repinfo in video_info.items() :
        title = idlist[vid]
        cdatestr = cdatelist[vid]
        cdate = dt.strptime(cdatestr, '%y/%m/%d')
        alldays = lastdate - cdate      
        fromdays = alldays.days + 1  #  登録日からの日数 初日を 1 とするため +1 する
        count = repinfo['replay']    #  全再生回数
        avarage = count / fromdays
        up = count - repinfo['prev_rep']  # 当日の再生回数  (全再生回数 - 前日の再生回数)
        weekup = count - repinfo['week_rep']
        monup = count - repinfo['mon_rep']
        monuprate = monup / count * 100
        mon3up = count - repinfo['mon3_rep']
        weekdays = 7
        monthdays = 30
        month3days = 90
        if fromdays < weekdays :
            weekdays = fromdays
        if fromdays < monthdays :
            monthdays = fromdays
        if fromdays < month3days :
            month3days = fromdays
        good_cnt = int(gooddata[vid])
        if vid in prev_gooddata :
            prev_good_cnt = int(prev_gooddata[vid])
            diff_good = good_cnt - prev_good_cnt
        else :
            diff_good = good_cnt

        out.write(f'<tr><td>{title}</td>'
                  f'<td align="right">{up}</td>'
                  f'<td align="right">{weekup}</td><td align="right">{weekup/weekdays:.2f}</td>'
                  f'<td align="right">{monup}</td><td align="right">{monup/monthdays:.2f}</td>'
                  f'<td align="right">{mon3up}</td><td align="right">{mon3up/month3days:.2f}</td>' 
                  f'<td align="right">{count}</td><td align="right">{avarage:.2f}</td>'
                  f'<td align="right">{cdatestr}</td>'
                  f'<td align="right">{monuprate:.2f}</td>'
                  f'<td align="right">{good_cnt}</td>'
                  f'<td align="right">{diff_good}</td></tr>\n')
        csvout.write(f'{title},{up},{weekup},{monup},{mon3up},{count},{cdatestr},{good_cnt}\n')

    csvout.close()

#  日ごとの再生回数を収めた辞書 daily_info を生成する
def create_daily_info() :
    global daily_info,mon_data,df_movav30,df_movav90,df_movav365
    df_dd = df.copy()   # df のdateにindexを設定するとdf['date']などがエラーになるのでコピー
    df_dd['date'] = pd.to_datetime(df_dd['date'])
    df_dd.set_index('date', inplace=True) 
    df_dd = df_dd.resample("D").sum()
    date_list = []
    replay_list = []
    old = -1
    for index, row in df_dd.iterrows():
        if old == -1 :    # 最初だけ
            old = row.replay
            continue 
        cnt = row.replay - old
        date_list.append(index)
        replay_list.append(cnt)
        daily_info[index] = cnt
        old = row.replay

    # 月ランキングのためのデータ mon_data 作成  現在月の 日付がキー  再生回数が値
    old = -1
    for index,row in df_dd.tail(31).iterrows():   # 過去31日分のデータを取得
        if old == -1 :    # 最初だけ
            old = row.replay
            continue 
        cnt = row.replay - old
        mon_data[index] = cnt
        old = row.replay

    df_movav30 = calc_dayly_movave(df_dd,30,7)
    df_movav90 = calc_dayly_movave(df_dd,90,7)
    df_movav365 = calc_dayly_movave(df_dd,365,7)

#  移動平均のためのデータ作成
# priod   作成する期間
# mov_ave_dd = 7   何日間の移動平均か
def calc_dayly_movave(df_dd,priod,mov_ave_dd) :
    old = -1
    mov_ave_cnt = []
    mov_ave_date = []
    for index,row in df_dd.tail(priod+mov_ave_dd).iterrows():   # 過去のデータを取得
        if old == -1 :    # 最初だけ
            old = row.replay
            continue 
        cnt = row.replay - old
        mov_ave_cnt.append(cnt)
        mov_ave_date.append(index)
        old = row.replay

    df_movav = pd.DataFrame(list(zip(mov_ave_date,mov_ave_cnt)), columns = ['date','cnt'])
    df_movav['cnt'] = df_movav['cnt'].rolling(7).mean()
    df_movav = df_movav.tail(priod)
    return df_movav

def monthly_rank():
    rank = {}
    rank = sorted(mon_data.items(), key=lambda x:x[1],reverse=True)
    rank = dict((x, y) for x, y in rank)
    rank_common(rank,1)

def monthly_rank2():
    rank = {}
    rank = sorted(mon_data.items(), key=lambda x:x[1],reverse=False)
    rank = dict((x, y) for x, y in rank)
    rank_common(rank,1)

def daily_rank1() :
    rank = {}
    rank = sorted(daily_info.items(), key=lambda x:x[1],reverse=True)
    rank = dict((x, y) for x, y in rank)
    rank_common(rank,1)

def daily_rank2() :
    rank = {}
    rank = sorted(daily_info.items(), key=lambda x:x[1],reverse=True)
    rank = dict((x, y) for x, y in rank)
    rank_common(rank,2)

def daily_rank3() :
    rank = {}
    rank = sorted(daily_info.items(), key=lambda x:x[1],reverse=False)
    rank = dict((x, y) for x, y in rank)
    rank_common(rank,1)

def daily_rank4() :
    rank = {}
    rank = sorted(daily_info.items(), key=lambda x:x[1],reverse=False)
    rank = dict((x, y) for x, y in rank)
    rank_common(rank,2)

def rank_common(rankdata,half) :
    i = 0
    base_date = datetime.datetime(2022, 11, 1)
    for chk_date,cnt in rankdata.items() :
        if cnt == 0 :
            continue
        #print(type(chk_date))
        if chk_date < base_date :
            continue 
        i = i + 1 
        if half == 1 :
            if i > 10 : 
                return
        else  :
            if i <= 10  : 
                continue
            if i >= 21  : 
                return

        chk_date = chk_date - datetime.timedelta(days=1)   # 実データと日付が1日ずれているので補正
        dd = chk_date.strftime('%Y/%m/%d')
        out.write(f'<tr><td align="right">{i}</td><td>{dd}</td><td align="right">{cnt}</td></tr>')


def post_pixela() :
    if debug == 1 :
        return
    post_days = 10      #  最近の何日をpostするか
    headers = {}
    headers['X-USER-TOKEN'] = pixela_token
    startdate =  lastdate - timedelta(post_days)
    for chk_date,cnt in daily_info.items() :
        if chk_date < startdate :
            continue
        data = {}
        dd = chk_date - datetime.timedelta(days=1)   # 実データと日付が1日ずれているので補正
        dd = dd.strftime('%Y%m%d') 
        data['date'] = dd
        data['quantity'] = str(cnt)
        response = requests.post(url=pixela_url, json=data, headers=headers,verify=False)

def daily_graph() :
    check_days = 30
    startdate =  lastdate - timedelta(check_days)
    for chk_date,cnt in daily_info.items() :
        if chk_date >= startdate :
            dd = chk_date - datetime.timedelta(days=1)   # 実データと日付が1日ずれているので補正
            dd = dd.day
            out.write(f"['{dd}',{cnt}],") 

#   移動平均
def move_ave_graph(flg) :     
    if flg == 30 :
        df_movav = df_movav30
    if flg == 90 :
        df_movav = df_movav90
    if flg == 365 :
        df_movav = df_movav365

    for _, row in df_movav.iterrows():
            mm = row.date.month
            dd = row.date.day
            out.write(f"['{mm}/{dd}',{row.cnt}],") 


def month_count():
    startyy = 2022
    endyy = 2024
    prev_replay = 0 
    for yy in range(startyy, endyy+1) :   
        dfyy = df[df['date'].dt.year == yy]
        if dfyy.empty :
            continue
        for mm in range(1,13) :
            dfyymm = dfyy[dfyy['date'].dt.month == mm]
            if dfyymm.empty :
                continue
            yymm = (yy - 2000) * 100 + mm
            lastdd = dfyymm.iloc[-1]['date']   # 月の最終日付
            endday = lastdd.day
            dflastday = dfyymm[dfyymm['date'] == lastdd]
            all_replay = dflastday['replay'].sum()  # 月の最終日付の総再生回数
            if prev_replay == 0 :
                firstday = dfyymm.iloc[0]['date']
                startday = firstday.day
                dffirstday = dfyymm[dfyymm['date'] == firstday]
                prev_replay = dffirstday['replay'].sum()
            else:
                startday = 0 

            month_replay = all_replay - prev_replay   # 今月の総再生回数
            prev_replay = all_replay
            monthly_info[yymm] = month_replay / (endday - startday)
    
def month_graph() :
    for chk_date,cnt in monthly_info.items() :
        out.write(f"['{chk_date}',{cnt}],") 

def parse_template() :
    global out 
    f = open(templatefile , 'r', encoding='utf-8')
    out = open(resultfile,'w' ,  encoding='utf-8')
    for line in f :
        if "%lastdate%" in line :
            curdate(line)
            continue
        if "replay_table" in line :
            output_replay_count2()
            continue
        if "%daily_graph%" in line :
            daily_graph()
            continue
        if "%move_ave_graph30%" in line :
            move_ave_graph(30)
            continue
        if "%move_ave_graph90%" in line :
            move_ave_graph(90)
            continue
        if "%move_ave_graph365%" in line :
            move_ave_graph(365)
            continue
        if "%month_graph%" in line :
            month_graph()
            continue
        if "%daily_rank1%" in line :
            daily_rank1()
            continue
        if "%daily_rank2%" in line :
            daily_rank2()
            continue
        if "%daily_rank3%" in line :
            daily_rank3()
            continue
        if "%daily_rank4%" in line :
            daily_rank4()
            continue
        if "%monthly_rank%" in line :
            monthly_rank()
            continue
        if "%monthly_rank2%" in line :
            monthly_rank2()
            continue
        if "%version%" in line :
            s = line.replace("%version%",version)
            out.write(s)
            continue
        if "%today%" in line :
            today(line)
            continue

        out.write(line)

    f.close()
    out.close()

def curdate(s) :
    s = s.replace("%lastdate%",str(lastdate))
    out.write(s)

def today(s):
    d = datetime.datetime.today().strftime("%m/%d %H:%M")
    s = s.replace("%today%",d)
    out.write(s)

def read_config() : 
    global ftp_host,ftp_user,ftp_pass,ftp_url,debug,pixela_url,pixela_token
    if not os.path.isfile(conffile) :
        debug = 1 
        return

    conf = open(conffile,'r', encoding='utf-8')
    ftp_host = conf.readline().strip()
    ftp_user = conf.readline().strip()
    ftp_pass = conf.readline().strip()
    ftp_url = conf.readline().strip()
    pixela_url = conf.readline().strip()
    pixela_token = conf.readline().strip()
    conf.close()

def ftp_upload() : 
    if debug == 1 :
        return 
    with FTP_TLS(host=ftp_host, user=ftp_user, passwd=ftp_pass) as ftp:
        ftp.storbinary('STOR {}'.format(ftp_url), open(resultfile, 'rb'))

# -------------------------------------------------------------
main_proc()
