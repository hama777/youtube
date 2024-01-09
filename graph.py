#!/usr/bin/python
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import os

version = "1.04"      #  23/09/17
pythonexe = "D:\AP\python\python.exe"
appdir = os.path.dirname(os.path.abspath(__file__))
dailydata = appdir + "\\dailydata.txt"
videoidf = appdir + "\\videoid.txt"
titlelist = []
title_to_id = {}
priod_list = ["7日","30日"]
target_list = ["すべて","6ヶ月","3ヶ月","1ヶ月"]
date_list = []
replay_list = []

button_css = f"""
<style>
  div.stButton > button:first-child  {{
    font-weight  : bold                ;/* 文字：太字                   */
    border       :  2px solid #03571f    ;/* 枠線：ピンク色で5ピクセルの実線 */
    border-radius: 10px 10px 10px 10px ;/* 枠線：半径10ピクセルの角丸     */
    background   : #a3d2f7             ;/* 背景色：薄いグレー            */
    width  : 120px
  }}
</style>
"""
target_df = ""  

def main_proc() :
    global target_df

    read_dailydata()
    read_videoid()

    st.markdown(button_css, unsafe_allow_html=True)

    title = '<p style="color:green; background-color:#a3d2f7;font-weight:bold;font-size: 24px;">再生回数推移</p>'
    st.markdown(title, unsafe_allow_html=True)
    selector=st.sidebar.selectbox( "曲選択",titlelist)
    ave_select =st.sidebar.selectbox( "日数",priod_list)
    target_select =st.sidebar.selectbox( "期間",target_list)

    if ave_select == "7日" :
        ave_priod = 7
    else :
        ave_priod = 30
    if target_select == "すべて" :
        target_days = -1
    if target_select == "6ヶ月" :
        target_days = 180
    if target_select == "3ヶ月" :
        target_days = 90
    if target_select == "1ヶ月" :
        target_days = 30

    select_id = title_to_id[selector]
    # date_list,replay_list を作成
    if select_id == "All" :
        create_data_for_all()
    else :
        create_data_for_vid(select_id)

    # date_list  replay_list  から df 作成
    graph_df = pd.DataFrame(list(zip(date_list,replay_list)), columns = ['date','cnt'])
    graph_df['mvave'] = graph_df['cnt'].rolling(ave_priod).mean()
    graph_df = graph_df[ave_priod:]   #  移動平均の最初はデータがないため削除
    if target_days != -1 :
        graph_df = graph_df.tail(target_days)
    
    st.line_chart(data=graph_df,                     # データソース
                x="date",               # X軸
                y="mvave",               # Y軸
                width=0,                     # 表示設定（幅）
                height=0,                    # 表示設定（高さ）
                use_container_width=True,    # True の場合、グラフの幅を列の幅に設定
                )

#  日付と再生回数のリスト date_list replay_list を作成
def create_data_for_all() :
    global date_list,replay_list
    df_dd = df.copy()   # df のdateにindexを設定するとdf['date']などがエラーになるのでコピー
    df_dd['date'] = pd.to_datetime(df_dd['date'])
    df_dd.set_index('date', inplace=True) 
    df_dd = df_dd.resample("D").sum()
    old = -1
    for index, row in df_dd.iterrows():
        if old == -1 :    # 最初だけ
            old = row.replay
            continue 
        cnt = row.replay - old
        date_list.append(index)
        replay_list.append(cnt)
        old = row.replay

#  vid の日付と再生回数のリスト date_list replay_list を作成
def create_data_for_vid(vid) :
    global date_list,replay_list
    tmp_df =   df[df['vid'] == vid]
    tmp_df = tmp_df.drop("vid",axis=1)

    old = -1
    for index, row in tmp_df.iterrows():
        if old == -1 :    # 最初だけ
            old = row.replay
            continue 
        cnt = row.replay - old
        date_list.append(row.date)
        replay_list.append(cnt)
        old = row.replay

def read_dailydata() :
    global df , lastdate
    df = pd.read_table(dailydata, names=('date', 'vid', 'replay'),parse_dates=[0])
    lastdate = df.iloc[-1]['date']

def read_videoid() :
    global titlelist,title_to_id
    idf = open(videoidf,'r', encoding='utf-8')
    for line in idf :
        line = line.strip()
        id,title,_ = line.split("\t")
        titlelist.append(title)
        title_to_id[title] = id

    idf.close()
    titlelist.append("All")
    title_to_id["All"] = "All"
    titlelist.reverse()

# -------------------------------------------------------------
main_proc()
