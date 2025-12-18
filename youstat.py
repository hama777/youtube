#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import datetime
import pandas as pd
import requests
from datetime import date,timedelta
from ftplib import FTP_TLS
from datetime import datetime as dt

# 25/12/18 v1.62 今月の順位を表示する
version = "1.62"

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
coverratefile = appdir + "./coverrate.txt" 
csvfile = appdir + "./replay.csv" 
selfmadefile = appdir + "./seftmade.txt"   # 自作曲の日々のリプライ数を保存する

idlist = {}       # キー videoid  値  タイトル
cdatelist = {}    # キー videoid  値  動画登録日
selflist = {}     # キー videoid  値  0 自作   1 その他
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
year_data = {}       
coverrate_info = {}  # 網羅率の履歴   キー  日付  値  リスト(日、週、月、3ヶ月 それぞれの網羅率)
ftp_host = ftp_user = ftp_pass = ftp_url =  ""
pixela_url = ""
pixela_token = ""

def main_proc() :
    date_settings()
    read_config()
    read_videoid()
    read_dailydata()
    read_good_data()
    read_coverrate()
    #read_selfmade_data()
    create_repcount_info()    
    create_daily_info()
    month_count()   
    create_selfmade_df()
    parse_template()
    output_covering_rate()
    ftp_upload()
    post_pixela()

#  video ID とタイトルの対応表読み込み
#     self_made は 0  自作  1  編曲
def read_videoid() :
    global idlist,cdatelist,selflist
    idf = open(videoidf,'r', encoding='utf-8')
    for line in idf :
        line = line.strip()
        id,title,cdate,self_made = line.split("\t")
        idlist[id] = title
        cdatelist[id] = cdate
        selflist[id] = int(self_made)
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

def read_coverrate() :
    global coverrate_info
    cf = open(coverratefile,'r', encoding='utf-8')
    for line in cf :
        line = line.strip()
        data = line.split("\t")
        datedata =  dt.strptime(data[0], '%y/%m/%d')
        coverrate_info[datedata] = data[1:] 
    cf.close()

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


# 再生回数情報 rep_info を参照し各期間の再生回数を出力する
def output_replay_count2() :
    csvout = open(csvfile,'w' ,  encoding='utf-8')
    csvout.write('タイトル,日,週,月,四半期,全期,投稿日,Good\n')
    key_list = ["week","mon","mon3","all"]     #  調査する期間
    days_list = {"week":7,"mon":30,"mon3":90}     #  調査する期間
    for vid,video_info in rep_info.items() :
        title = idlist[vid]
        cdatestr = cdatelist[vid]
        cdate = dt.strptime(cdatestr, '%y/%m/%d')
        alldays = lastdate - cdate      
        fromdays = alldays.days + 1  #  登録日からの日数 初日を 1 とするため +1 する
        
        good_cnt = int(gooddata[vid])
        if vid in prev_gooddata :
            prev_good_cnt = int(prev_gooddata[vid])
            diff_good = good_cnt - prev_good_cnt
        else :
            diff_good = good_cnt

        out.write(f'<tr><td>{title}</td>'
                  f'<td align="right">{video_info["day"]}</td>')

        for k in key_list :
            if k == "all" :
                days = fromdays
            else :
                if fromdays < days_list[k] :
                    days = fromdays
                else :
                    days = days_list[k]
            out.write(f'<td align="right">{video_info[k]}</td><td align="right">{video_info[k]/days:.2f}</td>')

        good_rate = good_cnt / video_info['all'] * 100     #  再生回数あたりのgood率
        good_per_month =  good_cnt / fromdays * 30
        diff_good_str = str(diff_good)
        if diff_good >= 1 :                                # good に増分がある時は赤字にする
            diff_good_str = f'<span class=red>{diff_good}</span>'

        out.write(f'<td align="right">{good_cnt}</td>'
                  f'<td align="right">{diff_good_str}</td>'
                  f'<td align="right">{good_rate:.2f}</td>'
                  f'<td align="right">{good_per_month:.2f}</td>'
                  f'<td align="right">{cdatestr}</td>'
                  f'</tr>\n')

    csvout.close()

def read_selfmade_data() :
    global df_selfmade
    # 読み込み時のカラム名を指定
    col_names = ["se_date", "d_cnt", "w_cnt", "m_cnt", "q_cnt",
                "d_rate", "w_rate", "m_rate", "q_rate"]

    # ファイル読み込み（タブ区切り）
    df_selfmade = pd.read_csv(
        selfmadefile,
        sep="\t",
        header=None,        # ヘッダ行がない場合
        names=col_names,    # カラム名を指定
        dtype={             # int/float列の型を指定
            "d_cnt": int, "w_cnt": int, "m_cnt": int, "q_cnt": int,
            "d_rate": float, "w_rate": float, "m_rate": float, "q_rate": float,
        },
        parse_dates=["se_date"],     # se_date を日付として読み込み
        date_parser=lambda x: pd.to_datetime(x, format="%y/%m/%d")
    )

#   自作曲 過去分表示
def selfmade_table(col) :
    n = 0
    for index,row in df_selfmade.tail(30).iterrows():   # 直近19件のみ表示
        n += 1
        if multi_col(n,col,15) :
            continue
        d = row['se_date']
        d = d - timedelta(days=1)     # 実際の日付と1日ずれているので -1 日する
        date_str = d.strftime("%m/%d")
        out.write(f'<tr><td>{date_str}</td><td align="right">{row["d_cnt"]}</td><td align="right">{row["d_rate"]:.1f}%</td>'
                  f'<td align="right">{row["w_cnt"]}</td><td align="right">{row["w_rate"]:.1f}%</td>'
                  f'<td align="right">{row["m_cnt"]}</td><td align="right">{row["m_rate"]:.1f}%</td>'
                  f'<td align="right">{row["q_cnt"]}</td><td align="right">{row["q_rate"]:.1f}%</td></tr>\n')

#   自作曲の再生回数情報  df_selfmade の作成
def create_selfmade_df() :
    # 本日分の計算
    day = 0 
    week = 0 
    mon = 0 
    mon3 = 0
    all_day = all_week = all_mon = all_mon3 = 0
    for vid,video_info in rep_info.items() :
        all_day += video_info["day"]
        all_week += video_info["week"]
        all_mon += video_info["mon"]
        all_mon3 += video_info["mon3"]
        if selflist[vid] != 0 :
            continue
        day += video_info["day"]
        week += video_info["week"]
        mon += video_info["mon"]
        mon3 += video_info["mon3"]

    day_rate = day / all_day * 100
    week_rate = week / all_week * 100
    mon_rate = mon / all_mon * 100
    mon3_rate = mon3 / all_mon3 * 100

    #  本日分のファイル出力
    f = open(selfmadefile,'a', encoding='utf-8')
    date_str = today_date.strftime("%y/%m/%d")
    f.write(f'{date_str}\t{day}\t{week}\t{mon}\t{mon3}\t{day_rate:.2f}\t{week_rate:.2f}\t{mon_rate:.2f}\t{mon3_rate:.2f}\n')
    f.close()

    # 改めてファイルを読み本日分を含めた df_selfmade を作成する
    read_selfmade_data()
    #print(df_selfmade)

def selfmade_graph() :
    for index,row in df_selfmade.tail(30).iterrows():   # 
        d = row['se_date']
        d = d - timedelta(days=1)     # 実際の日付と1日ずれているので -1 日する
        date_str = d.strftime("%d")
        cnt = row["d_cnt"]
        out.write(f"['{date_str}',{cnt}],") 
    
    # TODO: 直近のデータが対象になっていない selfmade_table を改造する必要あり


#   網羅率を取得する
def get_covering_rate() :
    key_list = ["day","week","mon","mon3"]     #  調査する期間
    cnt = {}
    rate = {}
    for k in key_list :
        cnt[k] = 0 
    for vid,video_info in rep_info.items() :
        for k in key_list :
            if video_info[k] != 0 :
                cnt[k] = cnt[k] + 1 

    sum = len(rep_info)
    for k in key_list :
        rate[k] = cnt[k] / sum * 100
    
    return rate

#   網羅率の表示
#   TODO:  直近40日までを表示する
def covering_rate(col) :
    n = 0 
    coverrate_last = dict(list(coverrate_info.items())[-39:])  #  上限40件 今日の分1件を引く
    #  ログの日付は前日のものなので日付は前日のものを表示する
    for k,v in coverrate_last.items() :
        n += 1
        if multi_col(n,col,20) :
            continue
        k = k - timedelta(days=1)
        date_str = k.strftime("%y/%m/%d")
        s = f'<tr><td>{date_str}</td><td align="right">{v[0]}</td><td align="right">{v[1]}</td>' \
            f'<td align="right">{v[2]}</td><td align="right">{v[3]}</td></tr>\n'
        out.write(s)

    if col == 1 :
        return 
    rate = get_covering_rate()
    d = yesterday.strftime("%y/%m/%d")
    s = f"<tr><td>{d}</td><td align='right'>{rate['day']:5.1f}</td><td align='right'>{rate['week']:5.1f}</td>" \
        f"<td align='right'>{rate['mon']:5.1f}</td><td align='right'>{rate['mon3']:5.1f}</td></tr>\n"
    out.write(s)

#   複数カラムの場合の判定
#     n  ...  何行目か     col ... 何カラム目か   limit .. 何行表示するか
#     表示しない場合(continueする場合) true を返す
def multi_col(n,col,limit) :
    if col == 1 :
        if n > limit :
            return True
    if col == 2 :
        if n <= limit :
            return True
    return False


#   網羅率の出力
#   TODO： 1日に2回実行したときは出力しないようにする
def output_covering_rate() :
    rate = get_covering_rate()
    f = open(coverratefile , 'a', encoding='utf-8')
    d = today_date.strftime("%y/%m/%d")
    s = f"{d}\t{rate['day']:5.1f}\t{rate['week']:5.1f}\t{rate['mon']:5.1f}\t{rate['mon3']:5.1f}\n"
    f.write(s)
    f.close()

#   網羅率グラフ
def covering_rate_graph() :
    coverrate_last = dict(list(coverrate_info.items())[-119:])  #  上限120件 今日の分1件を引く
    for k,v in coverrate_last.items() :
        k = k - timedelta(days=1)
        date_str = k.strftime("%m/%d")
        out.write(f"['{date_str}',{v[0]}],") 
    rate = get_covering_rate()
    d = yesterday.strftime("%m/%d")
    out.write(f"['{d}',{rate['day']}],")   #  前日の分は coverrate_info に含まれていないため

#  再生回数 top 
def output_top_repcount() :
    top_repcount_com("week")

def top_repcount_com(key) :
    n_order = 5   #  何位まで表示するか
    vid_list = []
    rep_list = []
    for vid,video_info in rep_info.items() :
        vid_list.append(vid)
        rep_list.append(video_info[key])

    df_repcnt = pd.DataFrame(list(zip(vid_list,rep_list)), columns = ['vid','repcnt'])
    sorted_df_repcnt  = df_repcnt.sort_values('repcnt',ascending=False)
    i = 0 
    for _,row  in sorted_df_repcnt.iterrows() :
        i += 1 
        title = idlist[row['vid']]
        out.write(f"<tr><td>{i}</td><td>{title}</td><td align='right'>{row['repcnt']}</td></tr>\n")
        if i >= n_order :
            break

#  日ごとの再生回数を収めた辞書 daily_info を生成する
def create_daily_info() :
    global daily_info,mon_data,year_data,df_movav30,df_movav90,df_movav365
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

    # 年、月ランキングのためのデータ year_data mon_data 作成  現在月の 日付がキー  再生回数が値
    old = -1
    i = 0 
    for index,row in df_dd.tail(365).iterrows():   # 過去31日分のデータを取得
        if old == -1 :    # 最初だけ
            old = row.replay
            continue 
        i += 1 
        cnt = row.replay - old
        if i  >= 365 - 30  :
            mon_data[index] = cnt
        year_data[index] = cnt
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

def year_rank():
    rank = {}
    rank = sorted(year_data.items(), key=lambda x:x[1],reverse=True)
    rank = dict((x, y) for x, y in rank)
    rank_common(rank,1)

def year_rank_min():
    rank = {}
    rank = sorted(year_data.items(), key=lambda x:x[1],reverse=False)
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
        date_str = chk_date.strftime('%y/%m/%d')
        dd = lastdate - datetime.timedelta(days=1)
        if  chk_date.date() == dd.date() :
            date_str = f'<span class=red>{date_str}</span>'

        out.write(f'<tr><td align="right">{i}</td><td>{date_str}</td><td align="right">{cnt}</td></tr>')

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
    endyy = today_yy
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

#   月別再生回数ランキング  flg 1  TOP  2  Low
def month_rank(flg) :
    sortflg = True
    if flg == 2 :
        sortflg = False

    rank = {}
    rank = sorted(monthly_info.items(), key=lambda x:x[1],reverse=sortflg)
    rank = dict((x, y) for x, y in rank)
    n = 0 
    for yymm,val in rank.items() :
        n += 1
        str_yymm = yymm
        if yymm == (today_yy-2000) * 100 + today_mm :
            str_yymm = f'<span class=red>{yymm}</span>'

        out.write(f'<tr><td align="right">{n}</td><td>{str_yymm}</td><td align="right">{val:5.2f}</td></tr>\n')
        if n >= 10 :
            break


def cur_month_rank() :
    yymm = (today_yy -2000) * 100 + today_mm
    r = get_month_rank(yymm)
    out.write(f'{r} 位 / {len(monthly_info)}\n')

#   yymmの順位を返す
def get_month_rank(yymm) :
    if yymm not in monthly_info:
        raise KeyError(f"{yymm} is not in monthly_info")
    target_value = monthly_info[yymm]

    # 値を昇順にソート（重複は1つにまとめる）
    sorted_values = sorted(set(monthly_info.values()))

    # 順位は1始まり
    return sorted_values.index(target_value) + 1

def month_ave_order() :
    df_mon = df.resample(rule = "ME").mean()
    order = int(df_mon.rank(method='min',ascending=False).iloc[-1].item())
    count = len(df_mon)
    return order,count


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
        if "%year_rank%" in line :
            year_rank()
            continue
        if "%year_rank_min%" in line :
            year_rank_min()
            continue
        if "%top_replay%" in line :
            top_repcount_com("day")
            continue
        if "%top_replay_week%" in line :
            top_repcount_com("week")
            continue
        if "%top_replay_month%" in line :
            top_repcount_com("mon")
            continue
        if "%top_replay_month3%" in line :
            top_repcount_com("mon3")
            continue
        if "%covering_rate1%" in line :
            covering_rate(1)
            continue
        if "%covering_rate2%" in line :
            covering_rate(2)
            continue
        if "%covering_rate_graph%" in line :
            covering_rate_graph()
            continue
        if "%month_rank_top%" in line :
            month_rank(1)
            continue
        if "%month_rank_low%" in line :
            month_rank(2)
            continue
        if "%cur_month_rank%" in line :
            cur_month_rank()
            continue
        if "%selfmade_table1%" in line :
            selfmade_table(1)
            continue
        if "%selfmade_table2%" in line :
            selfmade_table(2)
            continue
        if "%selfmade_graph%" in line :
            selfmade_graph()
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

def date_settings():
    global  today_date,today_mm,today_dd,today_yy,yesterday,today_datetime
    today_datetime = datetime.datetime.today()
    today_date = datetime.date.today()
    today_mm = today_date.month
    today_dd = today_date.day
    today_yy = today_date.year
    yesterday = today_date - timedelta(days=1)

def curdate(s) :
    s = s.replace("%lastdate%",str(lastdate))
    out.write(s)

def today(s):
    d = today_datetime.strftime("%m/%d %H:%M")
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
