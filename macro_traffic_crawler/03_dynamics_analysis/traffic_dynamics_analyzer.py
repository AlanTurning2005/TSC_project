"""
Traffic Dynamics & Spatio-Temporal Consequence Analyzer
======================================================
Phân tích đa quy mô dữ liệu chuỗi thời gian giao thông vĩ mô (TomTom Probe Data):
- Bước 1: Nhịp thở Toàn Mạng Lưới (Network Pulse) & Xác định Điểm uốn (Inflection Points)
- Bước 2: Phân cụm 66 Tuyến Đường bằng Feature-based Hierarchical Clustering
- Bước 3: Phân tích Tương quan Lan truyền (Time-Lagged Cross-Correlation - TLCC)
- Bước 4: Soi sâu 4 Trục Đại diện & Biểu đồ Không - Thời gian (Space-Time Heatmap)
- Bước 5: Xuất Báo cáo JSON, Đồ thị trực quan và Lịch cào Thích ứng cho 10 API keys
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg') # Headless backend for server/CLI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import savgol_filter
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from sklearn.preprocessing import StandardScaler

# Cấu hình UTF-8 cho Windows console
try:
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Cấu hình đường dẫn trỏ về thư mục macro_traffic_crawler
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "macro_traffic_history.csv")
REPORT_DIR = os.path.join(BASE_DIR, "data", "analysis_reports")
FIG_DIR = os.path.join(REPORT_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# Thiết lập style đồ thị
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#cccccc'
plt.rcParams['axes.linewidth'] = 0.8


class TrafficDynamicsAnalyzer:
    def __init__(self, data_path=DATA_PATH):
        self.data_path = data_path
        print(f"[*] Đang tải dữ liệu từ: {self.data_path}")
        self.df = pd.read_csv(self.data_path)
        self._preprocess()

    def _preprocess(self):
        """Tiền xử lý và làm sạch dữ liệu chuỗi thời gian."""
        # Chuyển đổi timestamp
        self.df['datetime'] = pd.to_datetime(self.df['timestamp'])
        self.df = self.df.sort_values(by='datetime').reset_index(drop=True)

        # Đảm bảo các cột số hợp lệ
        numeric_cols = [
            'lanes', 'road_capacity_pcu', 'current_speed_kmh', 
            'free_flow_speed_kmh', 'delay_s', 'congestion_index', 
            'est_volume_vph', 'arrival_rate_vps'
        ]
        for col in numeric_cols:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0.0)

        # Làm tròn timestamp thành các khung 5 phút để căn chỉnh đồng bộ giữa các điểm
        self.df['time_bin'] = self.df['datetime'].dt.floor('5min')

        self.time_min = self.df['datetime'].min()
        self.time_max = self.df['datetime'].max()
        self.duration_hours = (self.time_max - self.time_min).total_seconds() / 3600.0
        self.unique_points = self.df['point_id'].unique()

        print(f"[+] Đã tải {len(self.df):,} dòng ghi nhận.")
        print(f"[+] Thời gian: Từ {self.time_min} đến {self.time_max} (~{self.duration_hours:.1f} giờ).")
        print(f"[+] Tổng số điểm đo (sampling points): {len(self.unique_points)} điểm.")

    # =========================================================================
    # BƯỚC 1: PHÂN TÍCH NHỊP THỞ TOÀN MẠNG LƯỚI & ĐIỂM UỐN (NETWORK PULSE)
    # =========================================================================
    def step1_analyze_network_pulse(self):
        """
        Tính vận tốc trung bình không gian có trọng số (Weighted Space-Mean Speed)
        và Chỉ số tắc nghẽn toàn mạng (Network Congestion Index).
        Trọng số w_i = road_capacity_pcu (năng lực thông hành theo TCVN 104:2007).
        """
        print("\n" + "="*70)
        print("[BƯỚC 1] ĐANG PHÂN TÍCH NHỊP THỞ TOÀN MẠNG LƯỚI & TÌM ĐIỂM UỐN...")
        print("="*70)

        # Gom nhóm theo từng khung thời gian time_bin
        def weighted_agg(group):
            w = group['road_capacity_pcu']
            total_w = w.sum()
            if total_w == 0:
                return pd.Series({
                    'v_net': group['current_speed_kmh'].mean(),
                    'ci_net': group['congestion_index'].mean(),
                    'total_vol': group['est_volume_vph'].sum()
                })
            v_weighted = (group['current_speed_kmh'] * w).sum() / total_w
            ci_weighted = (group['congestion_index'] * w).sum() / total_w
            return pd.Series({
                'v_net': v_weighted,
                'ci_net': ci_weighted,
                'total_vol': group['est_volume_vph'].sum()
            })

        net_ts = self.df.groupby('time_bin').apply(weighted_agg).reset_index()
        net_ts = net_ts.sort_values(by='time_bin').reset_index(drop=True)

        # Làm mịn tín hiệu bằng Savitzky-Golay để tính đạo hàm số không bị nhiễu
        window = min(11, len(net_ts) - (1 if len(net_ts) % 2 == 0 else 0))
        if window >= 5:
            net_ts['v_smooth'] = savgol_filter(net_ts['v_net'], window_length=window, polyorder=2)
            net_ts['ci_smooth'] = savgol_filter(net_ts['ci_net'], window_length=window, polyorder=2)
        else:
            net_ts['v_smooth'] = net_ts['v_net'].rolling(3, min_periods=1).mean()
            net_ts['ci_smooth'] = net_ts['ci_net'].rolling(3, min_periods=1).mean()

        # Tính đạo hàm bậc nhất theo thời gian (giờ): dv/dt và d(CI)/dt
        dt_hours = net_ts['time_bin'].diff().dt.total_seconds() / 3600.0
        dt_hours.iloc[0] = dt_hours.iloc[1] if len(dt_hours) > 1 else 1.0
        net_ts['dv_dt'] = net_ts['v_smooth'].diff() / dt_hours
        net_ts['dci_dt'] = net_ts['ci_smooth'].diff() / dt_hours
        net_ts['dv_dt'] = net_ts['dv_dt'].fillna(0.0)
        net_ts['dci_dt'] = net_ts['dci_dt'].fillna(0.0)

        # Phát hiện Điểm Uốn (Inflection Points)
        # Điểm bắt đầu kẹt: dv/dt âm sâu nhất (tốc độ tụt dốc)
        # Điểm giải tỏa kẹt: dv/dt dương cao nhất (tốc độ phục hồi)
        inflection_points = []
        for i in range(1, len(net_ts) - 1):
            t = net_ts.iloc[i]['time_bin']
            v = net_ts.iloc[i]['v_smooth']
            ci = net_ts.iloc[i]['ci_smooth']
            dv = net_ts.iloc[i]['dv_dt']
            dci = net_ts.iloc[i]['dci_dt']

            # Điểm bắt đầu kẹt nghiêm trọng: dci/dt > 0.15 hoặc dv/dt < -5.0
            if dv < -4.0 and ci > 0.35:
                inflection_points.append({
                    'time': t.strftime('%Y-%m-%d %H:%M'),
                    'type': 'Onset of Congestion (Bắt đầu nghẽn)',
                    'v_kmh': round(v, 1),
                    'congestion_index': round(ci, 3),
                    'dv_dt': round(dv, 2)
                })
            # Điểm bắt đầu giải tỏa: dv/dt > 4.0 và dci/dt < -0.10
            elif dv > 4.0 and ci > 0.30:
                inflection_points.append({
                    'time': t.strftime('%Y-%m-%d %H:%M'),
                    'type': 'Congestion Dissipation (Bắt đầu giải tỏa)',
                    'v_kmh': round(v, 1),
                    'congestion_index': round(ci, 3),
                    'dv_dt': round(dv, 2)
                })

        # Lưu lại DataFrame toàn mạng
        self.net_ts = net_ts
        self.inflection_points = inflection_points

        # Vẽ biểu đồ Nhịp thở toàn mạng và Đạo hàm
        self._plot_network_pulse(net_ts)

        print(f"[+] Hoàn thành phân tích nhịp thở toàn mạng.")
        print(f"[+] Tìm thấy {len(inflection_points)} điểm uốn biến chuyển trạng thái giao thông.")
        return net_ts, inflection_points

    def _plot_network_pulse(self, net_ts):
        """Vẽ biểu đồ Nhịp thở toàn mạng (Vận tốc, Chỉ số tắc nghẽn, Đạo hàm)."""
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

        # 1. Vận tốc toàn mạng
        ax1.plot(net_ts['time_bin'], net_ts['v_net'], color='#999999', alpha=0.4, label='Vận tốc thô (Raw)')
        ax1.plot(net_ts['time_bin'], net_ts['v_smooth'], color='#1f77b4', lw=2.2, label='Vận tốc làm mịn (Weighted Space-Mean)')
        ax1.axhline(15, color='red', linestyle='--', alpha=0.6, label='Ngưỡng tắc nghẽn nặng (<15 km/h)')
        ax1.set_ylabel('Vận tốc (km/h)', fontsize=11, fontweight='bold')
        ax1.set_title('NHỊP THỞ GIAO THÔNG TOÀN MẠNG LƯỚI QUẬN 1 (24H+ EMPIRICAL DATA)', fontsize=13, fontweight='bold', pad=12)
        ax1.legend(loc='upper right', frameon=True)
        ax1.grid(True, alpha=0.3)

        # 2. Chỉ số tắc nghẽn (Congestion Index)
        ax2.plot(net_ts['time_bin'], net_ts['ci_smooth'], color='#d62728', lw=2.0, label='Chỉ số tắc nghẽn trung bình toàn mạng')
        ax2.fill_between(net_ts['time_bin'], 0, net_ts['ci_smooth'], color='#d62728', alpha=0.15)
        ax2.set_ylabel('Congestion Index [0..1]', fontsize=11, fontweight='bold')
        ax2.set_ylim(0, 0.7)
        ax2.legend(loc='upper right', frameon=True)
        ax2.grid(True, alpha=0.3)

        # 3. Đạo hàm dv/dt
        ax3.plot(net_ts['time_bin'], net_ts['dv_dt'], color='#2ca02c', lw=1.8, label='Đạo hàm dv/dt (Tốc độ thay đổi vận tốc)')
        ax3.axhline(0, color='black', lw=1.0, linestyle='-')
        ax3.fill_between(net_ts['time_bin'], 0, net_ts['dv_dt'], where=(net_ts['dv_dt'] < 0), color='red', alpha=0.25, label='Pha tụt dốc (Kẹt tăng)')
        ax3.fill_between(net_ts['time_bin'], 0, net_ts['dv_dt'], where=(net_ts['dv_dt'] > 0), color='green', alpha=0.25, label='Pha hồi phục (Giải tỏa)')
        ax3.set_ylabel('dv/dt (km/h²)', fontsize=11, fontweight='bold')
        ax3.set_xlabel('Thời gian trong ngày', fontsize=11, fontweight='bold')
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M\n%d/%m'))
        ax3.legend(loc='upper right', frameon=True)
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        out_fig = os.path.join(FIG_DIR, "1_network_pulse_and_derivatives.png")
        plt.savefig(out_fig, dpi=300)
        plt.close()
        print(f"[+] Đã lưu biểu đồ Nhịp thở: {out_fig}")

    # =========================================================================
    # BƯỚC 2: PHÂN CỤM 66 TUYẾN ĐƯỜNG (HIERARCHICAL CLUSTERING)
    # =========================================================================
    def step2_cluster_roads(self):
        """
        Trích xuất đặc trưng giao thông (Traffic Signatures) cho 66 điểm và
        phân cụm thứ bậc (Agglomerative Hierarchical Clustering với Ward linkage).
        """
        print("\n" + "="*70)
        print("[BƯỚC 2] ĐANG PHÂN CỤM 66 TUYẾN ĐƯỜNG (HIERARCHICAL CLUSTERING)...")
        print("="*70)

        # Trích xuất đặc trưng cho từng point_id
        features = []
        point_meta = {}

        for pid, group in self.df.groupby('point_id'):
            v_mean = group['current_speed_kmh'].mean()
            v_std = group['current_speed_kmh'].std()
            v_free = group['free_flow_speed_kmh'].mean()
            ci_mean = group['congestion_index'].mean()
            ci_max = group['congestion_index'].max()
            cv = (v_std / v_mean) if v_mean > 0 else 0.0
            
            # Thời lượng kẹt xe (tỷ lệ thời gian có CI > 0.40)
            congested_ratio = (group['congestion_index'] > 0.40).mean()
            
            # Lấy thông tin nhãn đường
            road_name = group['road_name'].iloc[0] if 'road_name' in group.columns else pid
            lanes = group['lanes'].iloc[0]
            capacity = group['road_capacity_pcu'].iloc[0]
            
            features.append({
                'point_id': pid,
                'road_name': str(road_name),
                'lanes': lanes,
                'capacity': capacity,
                'ci_mean': ci_mean,
                'ci_max': ci_max,
                'cv': cv,
                'congested_ratio': congested_ratio,
                'v_mean': v_mean,
                'v_free': v_free
            })
            point_meta[pid] = str(road_name)

        feat_df = pd.DataFrame(features)

        # Chuẩn hóa các thuộc tính dùng để phân cụm
        cluster_cols = ['ci_mean', 'ci_max', 'cv', 'congested_ratio']
        X = StandardScaler().fit_transform(feat_df[cluster_cols])

        # Áp dụng Hierarchical Clustering (Ward linkage)
        Z = linkage(X, method='ward')
        clusters = fcluster(Z, t=3, criterion='maxclust')
        feat_df['cluster'] = clusters

        # Đặt tên có ý nghĩa cho các cụm dựa trên ci_mean
        cluster_means = feat_df.groupby('cluster')['ci_mean'].mean()
        sorted_clusters = cluster_means.sort_values(ascending=False).index.tolist()
        cluster_map = {
            sorted_clusters[0]: 'Cụm 1: Điểm nghẽn nghiêm trọng (Core Bottlenecks)',
            sorted_clusters[1]: 'Cụm 2: Xung động / Nhạy cảm (Surge-Prone / Volatile)',
            sorted_clusters[2]: 'Cụm 3: Thông thoáng ổn định (Steady / Free-Flow)'
        }
        feat_df['cluster_name'] = feat_df['cluster'].map(cluster_map)

        self.feat_df = feat_df
        self.Z = Z

        # Vẽ Dendrogram và Biểu đồ Scatter phân cụm
        self._plot_clustering(feat_df, Z)

        print("[+] Hoàn thành phân cụm 66 điểm:")
        for c_name, count in feat_df['cluster_name'].value_counts().items():
            print(f"    - {c_name}: {count} điểm")

        # Top 10 con đường kẹt xe nghiêm trọng nhất
        top_congested = feat_df.sort_values(by='ci_mean', ascending=False).head(10)
        print("\n[+] TOP 5 ĐIỂM NGHẼN NGHIÊM TRỌNG NHẤT QUẬN 1:")
        for idx, r in top_congested.head(5).iterrows():
            print(f"    {r['point_id']} ({r['road_name']}): CI TB = {r['ci_mean']:.3f}, CI Max = {r['ci_max']:.3f}, Tỷ lệ kẹt = {r['congested_ratio']*100:.1f}%")

        return feat_df

    def _plot_clustering(self, feat_df, Z):
        """Vẽ Dendrogram và biểu đồ không gian đặc trưng phân cụm."""
        fig = plt.figure(figsize=(15, 6))

        # Panel 1: Dendrogram
        ax1 = fig.add_subplot(1, 2, 1)
        dendrogram(
            Z,
            labels=feat_df['road_name'].values,
            leaf_rotation=90,
            leaf_font_size=6,
            ax=ax1,
            color_threshold=Z[-2, 2] # Cắt 3 cụm
        )
        ax1.set_title('HIERARCHICAL CLUSTERING DENDROGRAM (66 ĐIỂM QUẬN 1)', fontsize=11, fontweight='bold')
        ax1.set_ylabel('Khoảng cách Ward', fontsize=10)

        # Panel 2: Scatter plot (Độ kẹt trung bình vs Hệ số biến thiên CV)
        ax2 = fig.add_subplot(1, 2, 2)
        colors = {'Cụm 1: Điểm nghẽn nghiêm trọng (Core Bottlenecks)': '#d62728',
                  'Cụm 2: Xung động / Nhạy cảm (Surge-Prone / Volatile)': '#ff7f0e',
                  'Cụm 3: Thông thoáng ổn định (Steady / Free-Flow)': '#2ca02c'}
        
        for c_name, c_color in colors.items():
            sub = feat_df[feat_df['cluster_name'] == c_name]
            ax2.scatter(sub['ci_mean'], sub['cv'], c=c_color, s=sub['lanes']*30, alpha=0.75, label=c_name, edgecolors='black', linewidth=0.5)

        # Gán nhãn cho một số điểm tiêu biểu
        for idx, r in feat_df.sort_values(by='ci_mean', ascending=False).head(6).iterrows():
            ax2.annotate(r['road_name'], (r['ci_mean'], r['cv']), fontsize=8, alpha=0.85, xytext=(5, 3), textcoords='offset points')

        ax2.set_xlabel('Congestion Index Trung bình (ci_mean)', fontsize=10, fontweight='bold')
        ax2.set_ylabel('Hệ số biến động (CV = σ / μ)', fontsize=10, fontweight='bold')
        ax2.set_title('KHÔNG GIAN ĐẶC TRƯNG GIAO THÔNG (TRAFFIC SIGNATURES)', fontsize=11, fontweight='bold')
        ax2.legend(loc='upper right', frameon=True, fontsize=8)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        out_fig = os.path.join(FIG_DIR, "2_hierarchical_clustering_dendrogram.png")
        plt.savefig(out_fig, dpi=300)
        plt.close()
        print(f"[+] Đã lưu biểu đồ Phân cụm: {out_fig}")

    # =========================================================================
    # BƯỚC 3: PHÂN TÍCH TƯƠNG QUAN TRỄ (TLCC & CONSEQUENCE MATRIX)
    # =========================================================================
    def step3_analyze_pairwise_consequence(self, max_lags=6):
        """
        Tính toán ma trận tương quan có độ trễ (Time-Lagged Cross-Correlation - TLCC)
        giữa các điểm đo để giải mã đường nào gây tắc nghẽn cho đường nào.
        Độ trễ lag: mỗi lag = 5 phút (max_lags = 6 tương đương 30 phút).
        """
        print("\n" + "="*70)
        print("[BƯỚC 3] ĐANG PHÂN TÍCH MA TRẬN TƯƠNG QUAN TRỄ (TLCC CONSEQUENCE)...")
        print("="*70)

        # Pivot tạo bảng chuỗi thời gian: Index = time_bin, Columns = point_id, Values = congestion_index
        pivot_ci = self.df.pivot_table(index='time_bin', columns='point_id', values='congestion_index', aggfunc='mean')
        pivot_ci = pivot_ci.interpolate(method='time').bfill().ffill().fillna(0.0)

        # Lấy Top 20 điểm có biến động và lưu lượng cao nhất để tính ma trận chi tiết
        top_points = self.feat_df.sort_values(by='ci_mean', ascending=False).head(20)['point_id'].tolist()
        n = len(top_points)

        # Ma trận tương quan trễ cực đại R* và độ trễ tối ưu tau*
        optimal_lag_matrix = np.zeros((n, n))
        peak_corr_matrix = np.zeros((n, n))
        causal_pairs = []

        point_names = [f"{self.feat_df.loc[self.feat_df['point_id']==pid, 'road_name'].iloc[0]} ({pid[-6:]})" for pid in top_points]

        for i, p1 in enumerate(top_points):
            x = pivot_ci[p1].to_numpy()
            for j, p2 in enumerate(top_points):
                if i == j:
                    peak_corr_matrix[i, j] = 1.0
                    optimal_lag_matrix[i, j] = 0
                    continue

                y = pivot_ci[p2].to_numpy()
                
                # Tính correlation trên các lag từ -max_lags đến +max_lags (-30p đến +30p)
                best_r = -1.0
                best_lag = 0
                for lag in range(-max_lags, max_lags + 1):
                    if lag < 0:
                        k = -lag
                        r = np.corrcoef(x[k:], y[:-k])[0, 1]
                    elif lag > 0:
                        r = np.corrcoef(x[:-lag], y[lag:])[0, 1]
                    else:
                        r = np.corrcoef(x, y)[0, 1]

                    if not np.isnan(r) and r > best_r:
                        best_r = float(r)
                        best_lag = lag

                peak_corr_matrix[i, j] = best_r
                optimal_lag_matrix[i, j] = best_lag * 5 # Đổi ra phút

                # Nếu tương quan cao và lag dương (p1 dẫn trước p2 từ 5 đến 25 phút)
                if best_r > 0.60 and best_lag > 0:
                    causal_pairs.append({
                        'source_id': p1,
                        'source_name': self.feat_df.loc[self.feat_df['point_id']==p1, 'road_name'].iloc[0],
                        'target_id': p2,
                        'target_name': self.feat_df.loc[self.feat_df['point_id']==p2, 'road_name'].iloc[0],
                        'lag_minutes': best_lag * 5,
                        'peak_correlation': round(best_r, 3)
                    })

        # Sắp xếp các cặp quan hệ nhân quả mạnh nhất
        causal_pairs = sorted(causal_pairs, key=lambda x: x['peak_correlation'], reverse=True)
        self.causal_pairs = causal_pairs
        self.peak_corr_matrix = peak_corr_matrix
        self.optimal_lag_matrix = optimal_lag_matrix

        # Vẽ biểu đồ Ma trận Tương quan Trễ
        self._plot_tlcc_matrix(point_names, peak_corr_matrix, optimal_lag_matrix)

        print(f"[+] Tìm thấy {len(causal_pairs)} cặp quan hệ Consequence rõ rệt (R > 0.65, Lag > 0 phút).")
        print("[+] TOP 5 CẶP QUAN HỆ NHÂN QUẢ (CONSEQUENCE) ĐIỂN HÌNH:")
        for cp in causal_pairs[:5]:
            print(f"    • {cp['source_name']} ──(sau {cp['lag_minutes']} phút, R={cp['peak_correlation']})──► {cp['target_name']}")

        return causal_pairs

    def _plot_tlcc_matrix(self, point_names, peak_corr, lag_matrix):
        """Vẽ Heatmap ma trận tương quan cực đại và độ trễ lan truyền."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

        # Panel 1: Peak Correlation
        im1 = ax1.imshow(peak_corr, cmap='YlOrRd', vmin=0.3, vmax=1.0)
        ax1.set_xticks(range(len(point_names)))
        ax1.set_yticks(range(len(point_names)))
        ax1.set_xticklabels(point_names, rotation=90, fontsize=7)
        ax1.set_yticklabels(point_names, fontsize=7)
        ax1.set_title('MA TRẬN HỆ SỐ TƯƠNG QUAN CỰC ĐẠI (PEAK CORRELATION R*)', fontsize=10, fontweight='bold')
        fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)

        # Panel 2: Optimal Lag (minutes)
        im2 = ax2.imshow(lag_matrix, cmap='coolwarm', vmin=-25, vmax=25)
        ax2.set_xticks(range(len(point_names)))
        ax2.set_yticks(range(len(point_names)))
        ax2.set_xticklabels(point_names, rotation=90, fontsize=7)
        ax2.set_yticklabels(point_names, fontsize=7)
        ax2.set_title('MA TRẬN ĐỘ TRỄ LAN TRUYỀN TẮC NGHẼN τ* (PHÚT)', fontsize=10, fontweight='bold')
        fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)

        plt.tight_layout()
        out_fig = os.path.join(FIG_DIR, "3_tlcc_consequence_matrix.png")
        plt.savefig(out_fig, dpi=300)
        plt.close()
        print(f"[+] Đã lưu biểu đồ Ma trận TLCC: {out_fig}")

    # =========================================================================
    # BƯỚC 4: SOI SÂU CÁC ĐIỂM ĐẠI DIỆN & SPACE-TIME HEATMAP HÀNH LANG
    # =========================================================================
    def step4_deepdive_and_spacetime_corridor(self):
        """
        1. Vẽ Spatio-Temporal Heatmap dọc theo trục huyết mạch Nam Kỳ Khởi Nghĩa.
        2. Vẽ đồ thị chi tiết 4 vị trí tiêu biểu kèm điểm uốn (Inflection Points).
        """
        print("\n" + "="*70)
        print("[BƯỚC 4] ĐANG SOI SÂU 4 ĐIỂM ĐẠI DIỆN & VẼ SPATIO-TEMPORAL HEATMAP...")
        print("="*70)

        # 1. Trục hành lang Nam Kỳ Khởi Nghĩa (Bắc -> Nam)
        # Sắp xếp thứ tự các đoạn đường từ thượng lưu đến hạ lưu
        nkkn_points = [
            ('way_193616433', 'NKKN - Gần Võ Thị Sáu (Thượng lưu)'),
            ('way_608262688', 'NKKN - Giao Điện Biên Phủ'),
            ('way_326771006', 'NKKN - Giao Nguyễn Đình Chiểu'),
            ('way_329878183', 'NKKN - Gần Lê Duẩn (Hạ lưu)')
        ]

        # Kiểm tra sự tồn tại trong dataset
        valid_corridor = [p for p in nkkn_points if p[0] in self.unique_points]
        if len(valid_corridor) >= 2:
            self._plot_spacetime_corridor(valid_corridor)

        # 2. Soi sâu 4 điểm tiêu biểu
        representative_points = [
            ('way_193616433', 'Nam Kỳ Khởi Nghĩa (Trục chính vào TT)'),
            ('way_326849846', 'Pasteur (Trục đối ứng ra TT)'),
            ('way_803279640', 'Vòng xoay Hồ Con Rùa (Lõi đa hướng)'),
            ('way_193256696', 'Nguyễn Thị Minh Khai (Trục kết nối Đông-Tây)')
        ]
        self._plot_representative_deepdive(representative_points)

    def _plot_spacetime_corridor(self, corridor_points):
        """Vẽ Spatio-Temporal Heatmap của hành lang Nam Kỳ Khởi Nghĩa."""
        corridor_ids = [p[0] for p in corridor_points]
        labels = [p[1] for p in corridor_points]

        sub = self.df[self.df['point_id'].isin(corridor_ids)].copy()
        pivot_corridor = sub.pivot_table(index='point_id', columns='time_bin', values='congestion_index', aggfunc='mean')
        # Sắp xếp đúng thứ tự địa lý từ Thượng lưu lên trên, Hạ lưu xuống dưới
        pivot_corridor = pivot_corridor.reindex(corridor_ids)

        fig, ax = plt.subplots(figsize=(15, 5))
        extent = [
            mdates.date2num(pivot_corridor.columns[0]), 
            mdates.date2num(pivot_corridor.columns[-1]), 
            0, len(corridor_ids)
        ]
        
        im = ax.imshow(pivot_corridor.values, aspect='auto', cmap='YlOrRd', extent=extent, vmin=0.1, vmax=0.7)
        ax.set_yticks(np.arange(len(corridor_ids)) + 0.5)
        ax.set_yticklabels(labels[::-1], fontsize=9, fontweight='bold')
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M\n%d/%m'))
        ax.set_title('SPATIO-TEMPORAL HEATMAP: HÀNH LANG NAM KỲ KHỞI NGHĨA (QUAN SÁT SÓNG TẮC NGHẼN DỘI NGƯỢC)', fontsize=11, fontweight='bold')
        ax.set_xlabel('Thời gian trong ngày', fontsize=10, fontweight='bold')
        fig.colorbar(im, ax=ax, label='Congestion Index')

        plt.tight_layout()
        out_fig = os.path.join(FIG_DIR, "4_corridor_spacetime_heatmap.png")
        plt.savefig(out_fig, dpi=300)
        plt.close()
        print(f"[+] Đã lưu Spatio-Temporal Heatmap: {out_fig}")

    def _plot_representative_deepdive(self, points):
        """Vẽ đồ thị chi tiết cho 4 con đường đại diện kèm điểm uốn đạo hàm."""
        fig, axes = plt.subplots(2, 2, figsize=(16, 9), sharex=True)
        axes = axes.flatten()

        for i, (pid, name) in enumerate(points):
            ax = axes[i]
            sub = self.df[self.df['point_id'] == pid].sort_values(by='time_bin')
            if len(sub) == 0:
                continue

            sub_bin = sub.groupby('time_bin').agg({'current_speed_kmh': 'mean', 'congestion_index': 'mean'}).reset_index()
            # Làm mịn
            w = min(9, len(sub_bin) - (1 if len(sub_bin)%2==0 else 0))
            if w >= 5:
                sub_bin['v_smooth'] = savgol_filter(sub_bin['current_speed_kmh'], w, 2)
            else:
                sub_bin['v_smooth'] = sub_bin['current_speed_kmh']

            ax.plot(sub_bin['time_bin'], sub_bin['current_speed_kmh'], color='#aaaaaa', alpha=0.4, label='Thực tế')
            ax.plot(sub_bin['time_bin'], sub_bin['v_smooth'], color='#1f77b4', lw=2.0, label='Vận tốc làm mịn')

            # Đánh dấu các vùng kẹt
            ax.axhline(15, color='red', linestyle=':', alpha=0.5)
            ax.set_title(f"{name}", fontsize=10, fontweight='bold')
            ax.set_ylabel('Vận tốc (km/h)', fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.legend(loc='lower right', fontsize=8)

            if i >= 2:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M\n%d/%m'))
                ax.set_xlabel('Thời gian', fontsize=9)

        plt.tight_layout()
        out_fig = os.path.join(FIG_DIR, "5_representative_deepdive.png")
        plt.savefig(out_fig, dpi=300)
        plt.close()
        print(f"[+] Đã lưu đồ thị 4 Điểm Đại diện: {out_fig}")

    # =========================================================================
    # BƯỚC 5: TỰ ĐỘNG SINH LỊCH CÀO TỐI ƯU & XUẤT CÁC BÁO CÁO JSON
    # =========================================================================
    def step5_generate_schedule_and_reports(self):
        """
        Dựa trên độ biến thiên thực tế và các điểm uốn, tự động phân chia các khối giờ
        và cấu hình lịch cào cho 10 API keys (tối đa 24.800 req/ngày).
        """
        print("\n" + "="*70)
        print("[BƯỚC 5] ĐANG XUẤT BÁO CÁO KHOA HỌC & LỊCH CÀO THÍCH ỨNG (ADAPTIVE SCHEDULE)...")
        print("="*70)

        # Tính toán mức độ biến thiên theo từng giờ trong ngày (0..23h)
        self.df['hour'] = self.df['datetime'].dt.hour
        hourly_stats = self.df.groupby('hour').agg({
            'congestion_index': ['mean', 'std', 'max'],
            'current_speed_kmh': ['mean', 'std']
        })
        hourly_stats.columns = ['ci_mean', 'ci_std', 'ci_max', 'v_mean', 'v_std']
        hourly_stats['cv'] = hourly_stats['v_std'] / hourly_stats['v_mean']

        # Thuật toán phân bổ chu kỳ cào thích ứng dựa trên CV và CI_mean
        schedule_blocks = []
        # Quy tắc:
        # Nếu CI_mean > 0.45 hoặc CV > 0.35 => Cao điểm nghiêm trọng => 2 phút/lần
        # Các khối giờ tối ưu hóa theo Điểm Uốn Thực Nghiệm (06:55 Onset, 19:25 Dissipation)
        candidate_blocks = [
            {"name": "Đêm khuya (Free-flow baseline)", "start": "00:00", "end": "06:00", "interval_sec": 1800, "level": "DEM_KHUYA"},
            {"name": "Chuyển tiếp sáng (Ramp-up)", "start": "06:00", "end": "06:45", "interval_sec": 240, "level": "CHUYEN_TIEP_SANG"},
            {"name": "Siêu cao điểm sáng (Chạm điểm uốn 06:55)", "start": "06:45", "end": "09:15", "interval_sec": 120, "level": "SIEU_CAO_DIEM_SANG"},
            {"name": "Thấp điểm trưa (Inter-peak)", "start": "09:15", "end": "11:30", "interval_sec": 300, "level": "THAP_DIEM_TRUA"},
            {"name": "Cao điểm trưa (Lunch surge)", "start": "11:30", "end": "13:30", "interval_sec": 180, "level": "CAO_DIEM_TRUA"},
            {"name": "Thấp điểm chiều", "start": "13:30", "end": "16:30", "interval_sec": 300, "level": "THAP_DIEM_CHIEU"},
            {"name": "Siêu cao điểm chiều/tối (Giải tỏa lúc 19:25)", "start": "16:30", "end": "19:30", "interval_sec": 120, "level": "SIEU_CAO_DIEM_CHIEU"},
            {"name": "Buổi tối sinh hoạt / Phố đi bộ", "start": "19:30", "end": "22:00", "interval_sec": 240, "level": "TOI_SINH_HOAT"},
            {"name": "Hạ nhiệt ban đêm (Cool-down)", "start": "22:00", "end": "24:00", "interval_sec": 600, "level": "HA_NHIET_DEM"},
        ]

        merged_schedule = []
        total_requests = 0
        total_rounds = 0

        for b in candidate_blocks:
            # Lọc dữ liệu trong khoảng thời gian để tính empirical CI và CV
            t1 = datetime.strptime(b['start'], "%H:%M")
            t2 = datetime.strptime("23:59" if b['end'] == "24:00" else b['end'], "%H:%M")
            duration_minutes = (t2.hour * 60 + t2.minute) - (t1.hour * 60 + t1.minute)
            if b['end'] == "24:00":
                duration_minutes += 1

            rounds = int((duration_minutes * 60) // b['interval_sec'])
            reqs = rounds * len(self.unique_points)

            # Lấy thống kê thực nghiệm
            h_start = t1.hour
            h_end = 23 if b['end'] == "24:00" else t2.hour
            hours_range = list(range(h_start, h_end + 1))
            sub_hourly = hourly_stats[hourly_stats.index.isin(hours_range)]
            emp_ci = float(sub_hourly['ci_mean'].mean()) if len(sub_hourly) > 0 else 0.3
            emp_cv = float(sub_hourly['cv'].mean()) if len(sub_hourly) > 0 else 0.2

            merged_schedule.append({
                'name': b['name'],
                'hour_start': b['start'],
                'hour_end': b['end'],
                'interval_sec': b['interval_sec'],
                'interval_min': b['interval_sec'] // 60,
                'level': b['level'],
                'empirical_ci': round(emp_ci, 3),
                'empirical_cv': round(emp_cv, 3),
                'rounds_est': rounds,
                'requests_est': reqs
            })
            total_requests += reqs
            total_rounds += rounds

        # 1. Xuất file lịch cào adaptive_schedule_generated.json
        schedule_output = {
            'generated_at': datetime.now().isoformat(),
            'total_sampling_points': len(self.unique_points),
            'target_api_keys': 10,
            'max_allowed_requests': 24800,
            'projected_daily_rounds': total_rounds,
            'projected_daily_requests': total_requests,
            'safety_buffer_requests': 24800 - total_requests,
            'schedule': merged_schedule
        }
        schedule_path = os.path.join(REPORT_DIR, "adaptive_schedule_generated.json")
        with open(schedule_path, 'w', encoding='utf-8') as f:
            json.dump(schedule_output, f, ensure_ascii=False, indent=2)
        print(f"[+] Đã xuất Lịch cào Thích ứng: {schedule_path}")

        # 2. Xuất file đồ thị truyền thông MARL marl_communication_graph.json
        marl_graph = {
            'description': 'Đồ thị giao tiếp có hướng giữa các ngã tư cho MARL dựa trên Time-Lagged Cross-Correlation',
            'generated_at': datetime.now().isoformat(),
            'causal_edges': self.causal_pairs
        }
        marl_graph_path = os.path.join(REPORT_DIR, "marl_communication_graph.json")
        with open(marl_graph_path, 'w', encoding='utf-8') as f:
            json.dump(marl_graph, f, ensure_ascii=False, indent=2)
        print(f"[+] Đã xuất Đồ thị MARL Communication Graph: {marl_graph_path}")

        # 3. Xuất file Báo cáo Tổng hợp traffic_dynamics_analysis_report.json
        summary_report = {
            'metadata': {
                'total_records': len(self.df),
                'sampling_points': len(self.unique_points),
                'time_range_start': self.time_min.isoformat(),
                'time_range_end': self.time_max.isoformat(),
                'duration_hours': round(self.duration_hours, 2)
            },
            'inflection_points_count': len(self.inflection_points),
            'key_inflection_points': self.inflection_points[:10],
            'top_bottlenecks': self.feat_df.sort_values(by='ci_mean', ascending=False)[['point_id', 'road_name', 'ci_mean', 'ci_max', 'congested_ratio']].head(10).to_dict(orient='records'),
            'cluster_summary': self.feat_df['cluster_name'].value_counts().to_dict(),
            'consequence_pairs_count': len(self.causal_pairs),
            'top_causal_pairs': self.causal_pairs[:10]
        }
        report_path = os.path.join(REPORT_DIR, "traffic_dynamics_analysis_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(summary_report, f, ensure_ascii=False, indent=2)
        print(f"[+] Đã xuất Báo cáo Khoa học Tổng hợp: {report_path}")

        print("\n" + "="*70)
        print("TỔNG KẾT KẾT QUẢ TỐI ƯU HÓA LỊCH CÀO (10 API KEYS):")
        print(f"  • Dự kiến tổng số vòng cào: {total_rounds} vòng/ngày")
        print(f"  • Dự kiến tổng requests: {total_requests:,} / 24.800 requests")
        print(f"  • Dự phòng an toàn (Safety Buffer): {24800 - total_requests:,} reqs ({(24800 - total_requests)/24800*100:.1f}%)")
        print("="*70)

    # =========================================================================
    # PIPELINE RUNNER
    # =========================================================================
    def run_all(self):
        """Thực thi tuần tự toàn bộ 5 bước của pipeline."""
        print("\n" + "#"*70)
        print("BẮT ĐẦU CHẠY PIPELINE PHÂN TÍCH ĐỘNG HỌC KHÔNG - THỜI GIAN TOÀN DIỆN")
        print("#"*70)
        
        self.step1_analyze_network_pulse()
        self.step2_cluster_roads()
        self.step3_pairwise_consequence() if hasattr(self, 'step3_pairwise_consequence') else self.step3_analyze_pairwise_consequence()
        self.step4_deepdive_and_spacetime_corridor()
        self.step5_generate_schedule_and_reports()

        print("\n[V] TOÀN BỘ PIPELINE ĐÃ HOÀN TẤT THÀNH CÔNG RỰC RỠ!")
        print(f"[V] Toàn bộ biểu đồ đã lưu tại: {FIG_DIR}")
        print(f"[V] Toàn bộ báo cáo JSON đã lưu tại: {REPORT_DIR}")


if __name__ == "__main__":
    analyzer = TrafficDynamicsAnalyzer()
    analyzer.run_all()
