import pyodbc
import pandas as pd
import datetime
import jpholiday
import numpy as np

# --- データベース接続設定 ---
def get_connection():
    # Azure SQL Server 接続情報
    conn_str = (
        "DRIVER={SQL Server};"
        "SERVER=azure.pisces2.ddo.jp;"
        "DATABASE=ps4444;"
        "UID=sa;"
        "PWD=Piscesapo5725"
    )
    return pyodbc.connect(conn_str)

# --- 共通ロジック：予約時間の計算 ---
def calculate_appointment_duration(row, cfg):
    try:
        t_s_raw = pd.to_datetime(row['開始'])
        t_e_raw = pd.to_datetime(row['終了'])
        cfg_s_raw = pd.to_datetime(cfg['s'])
        cfg_e_raw = pd.to_datetime(cfg['e'])

        if pd.isnull(t_s_raw) or pd.isnull(t_e_raw) or pd.isnull(cfg_s_raw) or pd.isnull(cfg_e_raw):
            return 0

        y_s = datetime.datetime.combine(datetime.date(2000, 1, 1), t_s_raw.time())
        y_e = datetime.datetime.combine(datetime.date(2000, 1, 1), t_e_raw.time())
        d_s = datetime.datetime.combine(datetime.date(2000, 1, 1), cfg_s_raw.time())
        d_e = datetime.datetime.combine(datetime.date(2000, 1, 1), cfg_e_raw.time())
        
        v_s, v_e = max(y_s, d_s), min(y_e, d_e)
        if v_s >= v_e: return 0
        
        net_total = (v_e - v_s).total_seconds() / 60
        if cfg.get('bs') and cfg.get('be'):
            t_bs_raw = pd.to_datetime(cfg['bs'])
            t_be_raw = pd.to_datetime(cfg['be'])
            if pd.notnull(t_bs_raw) and pd.notnull(t_be_raw):
                bs = datetime.datetime.combine(datetime.date(2000, 1, 1), t_bs_raw.time())
                be = datetime.datetime.combine(datetime.date(2000, 1, 1), t_be_raw.time())
                o_s, o_e = max(v_s, bs), min(v_e, be)
                overlap = max(0, (o_e - o_s).total_seconds() / 60) if o_s < o_e else 0
                net_total -= overlap
        return max(0, net_total)
    except:
        return 0

# --- タブ1：LINE分析 ---
def get_line_analysis(start_date, end_date):
    conn = get_connection()
    try:
        s_str = f"{start_date} 00:00:00"
        e_str = f"{end_date} 23:59:59"
        q_chart = f"SELECT CAST(作成日時 AS DATE) as 日付, COUNT(DISTINCT 患者ID) as 件数 FROM LINEマスタ WHERE 作成日時 BETWEEN '{s_str}' AND '{e_str}' GROUP BY CAST(作成日時 AS DATE) ORDER BY 日付"
        df_chart = pd.read_sql(q_chart, conn)
        df_chart['日付'] = df_chart['日付'].astype(str)
        total_all_time = pd.read_sql("SELECT COUNT(DISTINCT 患者ID) FROM LINEマスタ", conn).iloc[0, 0]
        total_patients_master = pd.read_sql("SELECT COUNT(ID) FROM 患者マスタN", conn).iloc[0, 0]
        return {
            "chart_data": df_chart.replace({np.nan: None}).to_dict(orient="records"),
            "total_all_time": int(total_all_time) if pd.notnull(total_all_time) else 0,
            "total_patients_master": int(total_patients_master) if pd.notnull(total_patients_master) else 0
        }
    finally:
        conn.close()

# --- タブ2：詳細名簿 ---
def get_patient_list(start_date, end_date, search_name=""):
    conn = get_connection()
    try:
        search_condition = f"AND A.[患者氏名] LIKE '%{search_name}%'" if search_name else ""
        query = f"""
        SELECT TOP 500
            CONVERT(VARCHAR, A.[日付], 23) AS 予約日, RTRIM(A.[時刻]) AS 予約開始時間, A.[患者ID], A.[患者氏名] AS 氏名,
            M.生年月日, CASE WHEN M.SEX = 1 THEN '男' WHEN M.SEX = 2 THEN '女' ELSE '不明' END AS 性別,
            ISNULL(A.[担当医], '') AS dr1, ISNULL(A.[衛生士], '') AS dh1, ISNULL(A.[治療内容], '') AS 処置
        FROM アポイントデータ AS A LEFT JOIN 患者マスタN AS M ON A.患者ID = M.ID
        WHERE A.[日付] BETWEEN '{start_date}' AND '{end_date}' AND A.[DEL] <> 'True' {search_condition}
        ORDER BY A.[日付] ASC, A.[時刻] ASC
        """
        df = pd.read_sql(query, conn)
        def calc_age(bday):
            try:
                if not bday: return "不明"
                b_date = pd.to_datetime(bday)
                return datetime.date.today().year - b_date.year - ((datetime.date.today().month, datetime.date.today().day) < (b_date.month, b_date.day))
            except: return "不明"
        if not df.empty:
            df['年齢'] = df['生年月日'].apply(calc_age)
            res = df[['予約日', '予約開始時間', '患者ID', '氏名', '年齢', '性別', 'dr1', 'dh1', '処置']]
            return res.replace({np.nan: None}).to_dict(orient="records")
        return []
    finally:
        conn.close()

# --- タブ3：チェア稼働統計 ---
def get_chair_stats(start_date, end_date, selected_waku_nos):
    conn = get_connection()
    try:
        waku_nos_str = ",".join(map(str, selected_waku_nos))
        cfg = {"s": "09:00", "e": "18:30", "bs": "13:00", "be": "14:30"}
        daily_capacity_min = 480 
        query = f"SELECT [日付], [時刻] AS 開始, [終了時刻] AS 終了, [横枠], [キャンセル] FROM アポイントデータ WHERE [日付] BETWEEN '{start_date}' AND '{end_date}' AND [横枠] IN ({waku_nos_str}) AND [DEL]<>'True'"
        df_raw = pd.read_sql(query, conn)
        df_active = df_raw[~df_raw['キャンセル'].astype(str).isin(['1', 'True', '1.0'])].copy()
        
        daily_records, chair_sums, active_days_count = [], {w: 0 for w in selected_waku_nos}, 0
        for d in pd.date_range(start_date, end_date):
            t_date = d.date()
            if jpholiday.is_holiday(t_date) or t_date.weekday() == 6: continue
            active_days_count += 1
            day_data = df_active[pd.to_datetime(df_active['日付']).dt.date == t_date]
            day_res_sum = day_data.apply(calculate_appointment_duration, axis=1, args=(cfg,)).sum() if not day_data.empty else 0
            for w in selected_waku_nos:
                w_data = day_data[day_data['横枠'] == w]
                if not w_data.empty: chair_sums[w] += w_data.apply(calculate_appointment_duration, axis=1, args=(cfg,)).sum()
            occ_rate = round((day_res_sum / (daily_capacity_min * len(selected_waku_nos)) * 100), 1) if len(selected_waku_nos) > 0 else 0
            daily_records.append({"date": str(t_date), "rate": float(occ_rate)})
            
        chair_breakdown = [{"unit": f"チェア{w}", "rate": float(round((s / (daily_capacity_min * active_days_count) * 100), 1))} for w, s in chair_sums.items()] if active_days_count > 0 else []
        avg = round(sum(d['rate'] for d in daily_records) / len(daily_records), 1) if daily_records else 0.0
        return {"daily_data": daily_records, "chair_breakdown": chair_breakdown, "average_rate": float(avg)}
    finally:
        conn.close()

# --- タブ4：新患リスト ---
def get_new_patients(start_date, end_date):
    conn = get_connection()
    try:
        query = f"""
        SELECT ID AS 患者ID, 氏名, 生年月日, CASE WHEN SEX = 1 THEN '男' WHEN SEX = 2 THEN '女' ELSE '不明' END AS 性別, CONVERT(VARCHAR, [作成日時], 23) AS 登録日
        FROM 患者マスタN WHERE [作成日時] BETWEEN '{start_date} 00:00:00' AND '{end_date} 23:59:59' ORDER BY [作成日時] DESC
        """
        df = pd.read_sql(query, conn)
        def calc_age(bday):
            try:
                if not bday: return "不明"
                b_date = pd.to_datetime(bday)
                return datetime.date.today().year - b_date.year - ((datetime.date.today().month, datetime.date.today().day) < (b_date.month, b_date.day))
            except: return "不明"
        if not df.empty:
            df['年齢'] = df['生年月日'].apply(calc_age)
            res = df[['登録日', '患者ID', '氏名', '年齢', '性別']]
            return res.replace({np.nan: None}).to_dict(orient="records")
        return []
    finally:
        conn.close()

# --- タブ5：キャンセル分析（新規実装） ---
def get_cancel_analysis_meta():
    """チェア名とスタッフ一覧をReactの選択肢として返す"""
    conn = get_connection()
    try:
        df_waku = pd.read_sql("SELECT ROW_NUMBER() OVER (ORDER BY コード) AS waku_no, 名称 FROM 枠マスタ", conn)
        df_staff = pd.read_sql("SELECT 区分, 記号 FROM スタッフマスタ", conn)
        return {
            "chairs": df_waku.to_dict(orient="records"),
            "staff": df_staff.to_dict(orient="records")
        }
    finally:
        conn.close()

def get_cancel_analysis(start_date, end_date, selected_waku_nos):
    conn = get_connection()
    try:
        nos_str = ",".join(map(str, selected_waku_nos))
        # 1. データ取得
        query = f"""
        SELECT A.[日付], A.[時刻], A.[患者ID], A.[患者氏名], A.[キャンセル], A.[f再診], A.[キャンセル理由], 
               A.[担当医], A.[衛生士], A.[IDCD], A.[治療内容], A.[治療内容2], A.[横枠],
               M.[LINE通知], M.[TEL通知], M.[Mail通知]
        FROM アポイントデータ AS A LEFT JOIN 患者マスタN AS M ON A.患者ID = M.ID
        WHERE A.[日付] BETWEEN '{start_date}' AND '{end_date}' AND A.[横枠] IN ({nos_str}) AND A.[DEL]<>'True'
        """
        df_raw = pd.read_sql(query, conn)
        if df_raw.empty: return None

        # 2. 前処理
        df_raw = df_raw[~df_raw['f再診'].astype(str).isin(['4', '4.0'])].copy()
        df_raw['日付_dt'] = pd.to_datetime(df_raw['日付']).dt.date
        df_raw['is_cancel'] = df_raw['キャンセル'].astype(str).isin(['1', 'True', '1.0'])
        df_raw['集計キー'] = df_raw.apply(lambda r: f"NAME_{r['患者氏名']}" if str(r['患者ID']).strip() in ['0', '', 'None', 'nan'] else f"ID_{r['患者ID']}", axis=1)
        df_raw['キャンセル理由'] = df_raw['キャンセル理由'].fillna('').str.strip().apply(lambda x: x if x != '' else '不明')

        # 3. リカバリー（再予約）チェック用のデータ取得
        cancelled_p_ids = df_raw[df_raw['is_cancel']]['患者ID'].unique()
        cancelled_p_names = df_raw[df_raw['is_cancel'] & df_raw['患者ID'].astype(str).isin(['0','','None','nan'])]['患者氏名'].unique()
        
        where_recovery = []
        if len(cancelled_p_ids) > 0:
            ids_clean = [str(int(float(x))) for x in cancelled_p_ids if str(x).strip() not in ['0','','None','nan']]
            if ids_clean: where_recovery.append(f"[患者ID] IN ({','.join(ids_clean)})")
        if len(cancelled_p_names) > 0:
            names_clean = [f"'{n}'" for n in cancelled_p_names]
            where_recovery.append(f"[患者氏名] IN ({','.join(names_clean)})")
        
        df_all_future = pd.DataFrame()
        if where_recovery:
            rec_query = f"SELECT [日付], [患者ID], [患者氏名] FROM アポイントデータ WHERE ({' OR '.join(where_recovery)}) AND [キャンセル]<>'True' AND [DEL]<>'True'"
            df_all_future = pd.read_sql(rec_query, conn)
            df_all_future['日付_dt'] = pd.to_datetime(df_all_future['日付']).dt.date

        # 4. 患者単位のユニークデータ集計
        df_unique = df_raw.groupby(['日付_dt', '集計キー']).agg({
            'is_cancel': 'max', 'キャンセル理由': 'first', '時刻': 'first', '患者ID': 'first', '患者氏名': 'first',
            '担当医': 'first', '衛生士': 'first', 'IDCD': 'first', '治療内容': 'first', '治療内容2': 'first',
            'LINE通知': 'first', 'TEL通知': 'first', 'Mail通知': 'first', '横枠': 'first'
        }).reset_index()

        # リカバリー判定
        def check_rec(r):
            if not r['is_cancel']: return False
            if df_all_future.empty: return False
            pid = str(r['患者ID']).strip()
            if pid not in ['0', '', 'None', 'nan']:
                try:
                    p_val = str(int(float(pid)))
                    match = df_all_future[(df_all_future['患者ID'].astype(str).str.contains(p_val)) & (df_all_future['日付_dt'] > r['日付_dt'])]
                except: return False
            else:
                match = df_all_future[(df_all_future['患者氏名'] == r['患者氏名']) & (df_all_future['日付_dt'] > r['日付_dt'])]
            return not match.empty
        
        df_unique['is_recovered'] = df_unique.apply(check_rec, axis=1)

        # 5. 各種集計
        # 日別推移
        daily = df_unique.groupby('日付_dt').agg(total=('is_cancel', 'count'), cancelled=('is_cancel', 'sum'), recovered=('is_recovered', 'sum')).reset_index()
        daily['rate'] = (daily['cancelled'] / daily['total'] * 100).round(1)
        daily['date'] = daily['日付_dt'].astype(str)

        # 理由内訳
        reasons = df_unique[df_unique['is_cancel']]['キャンセル理由'].value_counts().reset_index()
        reasons.columns = ['reason', 'count']

        # チェア別
        chair_meta = pd.read_sql("SELECT ROW_NUMBER() OVER (ORDER BY コード) AS waku_no, 名称 FROM 枠マスタ", conn)
        chair_map = chair_meta.set_index('waku_no')['名称'].to_dict()
        df_chair = df_unique.groupby('横枠').agg(total=('is_cancel', 'count'), cancelled=('is_cancel', 'sum')).reset_index()
        df_chair['unit'] = df_chair['横枠'].map(chair_map)
        df_chair['rate'] = (df_chair['cancelled'] / df_chair['total'] * 100).round(1)

        # 曜日・時間帯
        w_m = {0: '月', 1: '火', 2: '水', 3: '木', 4: '金', 5: '土', 6: '日'}
        df_unique['weekday'] = pd.to_datetime(df_unique['日付_dt']).dt.weekday.map(w_m)
        df_unique['hour'] = pd.to_datetime(df_unique['時刻'], errors='coerce').dt.hour
        
        weekday_stats = df_unique.groupby('weekday').agg(total=('is_cancel', 'count'), cancelled=('is_cancel', 'sum')).reset_index()
        weekday_stats['rate'] = (weekday_stats['cancelled'] / weekday_stats['total'] * 100).round(1)

        hour_stats = df_unique.dropna(subset=['hour']).groupby('hour').agg(total=('is_cancel', 'count'), cancelled=('is_cancel', 'sum')).reset_index()
        hour_stats['rate'] = (hour_stats['cancelled'] / hour_stats['total'] * 100).round(1)

        # スタッフ別 (Dr / DH)
        staff_meta = pd.read_sql("SELECT 区分, 記号 FROM スタッフマスタ", conn)
        dr_list = staff_meta[staff_meta['区分'] == 1]['記号'].tolist()
        dh_list = staff_meta[staff_meta['区分'] == 6]['記号'].tolist()
        
        df_unique['dr_label'] = df_unique['担当医'].str.strip().apply(lambda x: x if x in dr_list else 'その他')
        df_unique['dh_label'] = df_unique['衛生士'].str.strip().apply(lambda x: x if x in dh_list else 'その他')
        
        dr_stats = df_unique.groupby('dr_label').agg(total=('is_cancel', 'count'), cancelled=('is_cancel', 'sum')).reset_index()
        dr_stats['rate'] = (dr_stats['cancelled'] / dr_stats['total'] * 100).round(1)
        
        dh_stats = df_unique.groupby('dh_label').agg(total=('is_cancel', 'count'), cancelled=('is_cancel', 'sum')).reset_index()
        dh_stats['rate'] = (dh_stats['cancelled'] / dh_stats['total'] * 100).round(1)

        # 名簿
        def get_remind(r):
            if r['LINE通知'] == 1: return 'LINE'
            if r['TEL通知'] == 1: return 'SMS'
            if r['Mail通知'] == 1: return 'email'
            return '設定なし'
        df_unique['remind'] = df_unique.apply(get_remind, axis=1)
        cancel_list = df_unique[df_unique['is_cancel']].copy()
        cancel_list['staff'] = cancel_list['担当医'].fillna('') + ' / ' + cancel_list['衛生士'].fillna('')
        cancel_list['treatment'] = cancel_list['治療内容'].fillna('') + ' ' + cancel_list['治療内容2'].fillna('')
        cancel_list_final = cancel_list[['日付_dt', 'IDCD', '患者氏名', 'staff', 'treatment', 'キャンセル理由', 'remind', 'is_recovered']].rename(columns={'日付_dt': 'date', '患者氏名': 'name', 'キャンセル理由': 'reason', 'is_recovered': 'recovered'})

        return {
            "summary": {
                "total_appointments": int(df_unique.shape[0]),
                "cancel_count": int(df_unique['is_cancel'].sum()),
                "recovery_count": int(df_unique['is_recovered'].sum()),
                "cancel_rate": float(round(df_unique['is_cancel'].sum() / df_unique.shape[0] * 100, 1)) if df_unique.shape[0] > 0 else 0
            },
            "daily_transition": daily[['date', 'rate', 'cancelled', 'recovered']].to_dict(orient="records"),
            "reason_breakdown": reasons.to_dict(orient="records"),
            "chair_breakdown": df_chair[['unit', 'rate', 'cancelled']].to_dict(orient="records"),
            "weekday_breakdown": weekday_stats.to_dict(orient="records"),
            "hour_breakdown": hour_stats.to_dict(orient="records"),
            "dr_breakdown": dr_stats.to_dict(orient="records"),
            "dh_breakdown": dh_stats.to_dict(orient="records"),
            "cancel_list": cancel_list_final.astype(str).to_dict(orient="records")
        }
    finally:
        conn.close()