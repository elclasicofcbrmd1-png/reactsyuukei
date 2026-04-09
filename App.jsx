import React, { useState, useEffect } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, Legend, PieChart, Pie
} from 'recharts';
import { Search, XCircle, Bell, Filter } from 'lucide-react';

export default function App() {
  // --- 状態管理 (State) ---
  const [activeTab, setActiveTab] = useState('line');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // 分析期間の状態
  const [startDate, setStartDate] = useState('2025-03-01');
  const [endDate, setEndDate] = useState('2026-03-31');
  
  // 各データの保存箱
  const [lineData, setLineData] = useState(null);
  const [patientData, setPatientData] = useState([]);
  const [cancelData, setCancelData] = useState(null);
  
  // サブ状態
  const [cancelSubTab, setCancelSubTab] = useState('transition');
  const [searchTerm, setSearchTerm] = useState('');

  // --- データ取得関数 (Functions) ---

  // 1. LINE分析
  const fetchLineAnalysis = async () => {
    setLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/line-analysis?start=${startDate}&end=${endDate}`);
      const json = await res.json();
      setLineData(json);
    } catch (err) {
      setError("データの取得に失敗しました。サーバーが動いているか確認してください。");
    } finally {
      setLoading(false);
    }
  };

  // 2. 詳細名簿
  const fetchPatientList = async (name = "") => {
    setLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/patient-list?start=${startDate}&end=${endDate}&name=${name}`);
      const json = await res.json();
      setPatientData(json);
    } catch (err) {
      setError("名簿の取得に失敗しました。");
    } finally {
      setLoading(false);
    }
  };

  // 3. キャンセル分析
  const fetchCancelAnalysis = async () => {
    setLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/cancel-analysis?start=${startDate}&end=${endDate}&wakus=1,2,3,4,5,6,7`);
      const json = await res.json();
      setCancelData(json);
    } catch (err) {
      setError("キャンセル分析の取得に失敗しました。");
    } finally {
      setLoading(false);
    }
  };

  // 各タブ内の「実行ボタン」用
  const refreshCurrentTabData = () => {
    setError(null);
    if (activeTab === 'line') fetchLineAnalysis();
    if (activeTab === 'list') fetchPatientList(searchTerm);
    if (activeTab === 'cancel') fetchCancelAnalysis();
  };

  // 初回表示時
  useEffect(() => {
    fetchLineAnalysis();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans text-slate-800">
      
      {/* ヘッダー */}
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          🏥 歯科医院 運営ダッシュボード
        </h1>
        <p className="text-slate-500">必要な分析データをリアルタイムで確認します</p>
      </header>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg shadow-sm">
          ⚠️ {error}
        </div>
      )}

      {/* メインタブメニュー */}
      <nav className="flex flex-wrap gap-2 mb-4">
        {[
          { id: 'line', label: 'LINE分析', icon: <Bell className="w-4 h-4"/> },
          { id: 'list', label: '詳細名簿', icon: <Search className="w-4 h-4"/> },
          { id: 'cancel', label: 'キャンセル分析', icon: <XCircle className="w-4 h-4"/> }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id);
              // タブ切り替え時に自動でその期間のデータを取得
              if (tab.id === 'line') fetchLineAnalysis();
              if (tab.id === 'list') fetchPatientList(searchTerm);
              if (tab.id === 'cancel') fetchCancelAnalysis();
            }}
            className={`flex items-center gap-2 px-6 py-3 rounded-t-xl font-bold transition-all ${
              activeTab === tab.id 
                ? 'bg-white text-slate-900 border-t border-l border-r border-slate-200' 
                : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </nav>

      {/* 表示エリア */}
      <div className="bg-white rounded-b-xl rounded-tr-xl shadow-lg border border-slate-200 p-6 min-h-[500px]">
        
        {/* --- 1. LINE分析タブ --- */}
        {activeTab === 'line' && (
          <div className="space-y-6">
            <FilterSection 
              startDate={startDate} setStartDate={setStartDate} 
              endDate={endDate} setEndDate={setEndDate} 
              onExecute={refreshCurrentTabData} loading={loading}
            />
            {lineData && !loading && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
                <StatCard label="LINE全期間 累計登録" value={lineData.total_all_time} unit="名" color="bg-blue-600" />
                <StatCard label="カルテ総患者数" value={lineData.total_patients_master} unit="名" color="bg-emerald-600" />
              </div>
            )}
          </div>
        )}

        {/* --- 2. 詳細名簿タブ --- */}
        {activeTab === 'list' && (
          <div className="space-y-6">
            <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
              <FilterSection 
                startDate={startDate} setStartDate={setStartDate} 
                endDate={endDate} setEndDate={setEndDate} 
                onExecute={refreshCurrentTabData} loading={loading}
              />
              <div className="flex gap-2">
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                  <input 
                    type="text" 
                    placeholder="患者名で検索..." 
                    className="pl-10 pr-4 py-2 border border-slate-200 rounded-lg outline-none w-64 focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <button 
                  onClick={() => fetchPatientList(searchTerm)}
                  className="bg-slate-800 text-white px-5 py-2 rounded-lg hover:bg-black font-bold transition-colors text-sm"
                >
                  検索
                </button>
              </div>
            </div>
            {!loading && <DataTable data={patientData} />}
          </div>
        )}

        {/* --- 3. キャンセル分析タブ --- */}
        {activeTab === 'cancel' && (
          <div className="space-y-6">
            <FilterSection 
              startDate={startDate} setStartDate={setStartDate} 
              endDate={endDate} setEndDate={setEndDate} 
              onExecute={refreshCurrentTabData} loading={loading}
            />
            
            {cancelData && !loading && (
              <div className="space-y-6 pt-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <StatMini label="対象予約" value={cancelData.summary.total_appointments} unit="名" />
                  <StatMini label="キャンセル" value={cancelData.summary.cancel_count} unit="名" />
                  <StatMini label="キャンセル率" value={cancelData.summary.cancel_rate} unit="%" color="text-red-600" />
                  <StatMini label="リカバリー成功" value={cancelData.summary.recovery_count} unit="名" color="text-emerald-600" />
                </div>

                <div className="flex border-b border-slate-100 overflow-x-auto scrollbar-hide">
                  {[
                    { id: 'transition', label: '推移' },
                    { id: 'list', label: '名簿' },
                    { id: 'chair', label: 'チェア別' },
                    { id: 'staff', label: 'スタッフ別' },
                    { id: 'reason', label: '理由' }
                  ].map(st => (
                    <button
                      key={st.id}
                      onClick={() => setCancelSubTab(st.id)}
                      className={`px-5 py-2.5 whitespace-nowrap text-sm font-bold border-b-2 transition-colors ${
                        cancelSubTab === st.id ? 'border-slate-800 text-slate-800' : 'border-transparent text-slate-400 hover:text-slate-600'
                      }`}
                    >
                      {st.label}
                    </button>
                  ))}
                </div>

                <div className="pt-2 h-80">
                  {cancelSubTab === 'transition' && <ChartLine data={cancelData.daily_transition} xKey="date" yKey="rate" color="#ef4444" />}
                  {cancelSubTab === 'list' && <DataTable data={cancelData.cancel_list} />}
                  {cancelSubTab === 'chair' && <ChartBar data={cancelData.chair_breakdown} xKey="unit" yKey="rate" color="#f87171" />}
                  {cancelSubTab === 'reason' && (
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={cancelData.reason_breakdown} dataKey="count" nameKey="reason" cx="50%" cy="50%" outerRadius={100} label>
                          {cancelData.reason_breakdown.map((_, i) => (
                            <Cell key={i} fill={['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#6366f1'][i % 5]} />
                          ))}
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  )}
                  {cancelSubTab === 'staff' && (
                     <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
                        <div className="h-full">
                          <p className="text-center text-xs font-bold text-slate-400 mb-2">担当医別 (%)</p>
                          <ChartBar data={cancelData.dr_breakdown} xKey="dr_label" yKey="rate" color="#10b981" />
                        </div>
                        <div className="h-full">
                          <p className="text-center text-xs font-bold text-slate-400 mb-2">衛生士別 (%)</p>
                          <ChartBar data={cancelData.dh_breakdown} xKey="dh_label" yKey="rate" color="#f59e0b" />
                        </div>
                     </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <div className="w-10 h-10 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin"></div>
            <p className="text-slate-400 font-medium animate-pulse">データを集計しています...</p>
          </div>
        )}
      </div>
    </div>
  );
}

// --- 共通部品 (Sub Components) ---

// 期間選択セクション
function FilterSection({ startDate, setStartDate, endDate, setEndDate, onExecute, loading }) {
  return (
    <div className="flex flex-wrap items-end gap-3 p-4 bg-slate-50 rounded-xl border border-slate-100">
      <div className="space-y-1">
        <label className="text-[10px] font-black uppercase text-slate-400 tracking-wider ml-1">分析開始日</label>
        <input 
          type="date" 
          className="block px-3 py-1.5 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
      </div>
      <div className="text-slate-300 pb-2">〜</div>
      <div className="space-y-1">
        <label className="text-[10px] font-black uppercase text-slate-400 tracking-wider ml-1">分析終了日</label>
        <input 
          type="date" 
          className="block px-3 py-1.5 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
      </div>
      <button 
        onClick={onExecute}
        disabled={loading}
        className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg font-bold shadow-sm transition-all flex items-center gap-2 disabled:bg-slate-300 text-sm h-[38px]"
      >
        <Filter className="w-4 h-4"/> {loading ? '実行中...' : '分析を実行'}
      </button>
    </div>
  );
}

function StatCard({ label, value, unit, color }) {
  return (
    <div className={`${color} p-6 rounded-2xl text-white shadow-md`}>
      <p className="opacity-80 text-xs font-bold mb-1">{label}</p>
      <h2 className="text-4xl font-black">{value.toLocaleString()} <span className="text-lg font-normal">{unit}</span></h2>
    </div>
  );
}

function StatMini({ label, value, unit, color = "text-slate-800" }) {
  return (
    <div className="bg-white p-3 rounded-xl border border-slate-100 shadow-sm">
      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-tight">{label}</p>
      <h3 className={`text-xl font-black ${color}`}>{value} <span className="text-sm font-normal">{unit}</span></h3>
    </div>
  );
}

function DataTable({ data }) {
  if (!data || data.length === 0) return <div className="py-20 text-center text-slate-400 italic">指定された条件のデータは見つかりませんでした</div>;
  const headers = Object.keys(data[0]);
  return (
    <div className="overflow-x-auto border border-slate-100 rounded-xl">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 border-b border-slate-100 text-slate-500">
          <tr>
            {headers.map(h => <th key={h} className="p-4 font-bold">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {data.map((row, i) => (
            <tr key={i} className="hover:bg-blue-50/30 transition-colors">
              {headers.map(h => (
                <td key={h} className="p-4">
                  {row[h] === "True" || row[h] === "recovered" ? (
                    <span className="inline-flex items-center justify-center w-5 h-5 bg-emerald-100 text-emerald-600 rounded-full text-xs font-bold">✓</span>
                  ) : (
                    row[h]
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartLine({ data, xKey, yKey, color = "#2563eb" }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
        <XAxis dataKey={xKey} fontSize={10} stroke="#94a3b8" tickMargin={10} />
        <YAxis fontSize={10} stroke="#94a3b8" />
        <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
        <Line type="monotone" dataKey={yKey} stroke={color} strokeWidth={3} dot={{ r: 3, fill: color }} activeDot={{ r: 6 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function ChartBar({ data, xKey, yKey, color = "#6366f1" }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
        <XAxis dataKey={xKey} fontSize={10} stroke="#94a3b8" tickMargin={10} />
        <YAxis fontSize={10} stroke="#94a3b8" />
        <Tooltip cursor={{fill: '#f8fafc'}} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
        <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}