from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import database

app = FastAPI()

# React（フロントエンド）からのアクセスを許可するための設定（CORS）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """サーバーの動作確認用"""
    return {"status": "ok", "message": "Dental Clinic API is running"}

# --- タブ1: LINE分析用 ---
@app.get("/api/line-analysis")
def get_line_report(start: str, end: str):
    return database.get_line_analysis(start, end)

# --- タブ2: 詳細名簿用（検索機能付き） ---
@app.get("/api/patient-list")
def get_patients(start: str, end: str, name: str = ""):
    return database.get_patient_list(start, end, name)

# --- タブ3: チェア稼働統計用 ---
@app.get("/api/chair-stats")
def get_chair_report(start: str, end: str, wakus: str):
    """wakus は '1,2,3' 形式の文字列で届くのでリストに変換"""
    waku_ids = [int(x) for x in wakus.split(",")]
    return database.get_chair_stats(start, end, waku_ids)

# --- タブ4: 新患リスト用 ---
@app.get("/api/new-patients")
def get_new_patient_list(start: str, end: str):
    return database.get_new_patients(start, end)

# --- タブ5: キャンセル分析用 (メタ情報) ---
@app.get("/api/cancel-analysis-meta")
def get_cancel_meta():
    """チェア名やスタッフ一覧の選択肢を取得"""
    return database.get_cancel_analysis_meta()

# --- タブ5: キャンセル分析用 (集計データ) ---
@app.get("/api/cancel-analysis")
def get_cancel_report(start: str, end: str, wakus: str):
    """指定された期間とチェアのキャンセル状況を分析"""
    waku_ids = [int(x) for x in wakus.split(",")]
    return database.get_cancel_analysis(start, end, waku_ids)