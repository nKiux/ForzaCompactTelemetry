import socket
import struct
import tkinter as tk
import threading

# --- Forza 遙測設定 ---
UDP_IP = "127.0.0.1"
UDP_PORT = 12350  

class ForzaTelemetryOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Forza Telemetry HUD")
        # 視窗初始化設置：大小、位置、無邊框、置頂、半透明、背景色
        self.root.geometry("440x260+50+50") 
        self.root.overrideredirect(True)    
        self.root.attributes("-topmost", True) 
        self.root.attributes("-alpha", 0.85)   
        self.root.configure(bg='#1e1e1e')      

        font_main = ("Helvetica", 14, "bold")
        font_highlight = ("Helvetica", 16, "bold")

        # 引擎數據標籤
        self.lbl_rpm = tk.Label(self.root, text="轉速 (RPM): 0", fg="#00ff00", bg="#1e1e1e", font=font_main)
        self.lbl_rpm.pack(anchor="w", padx=10, pady=2)

        self.lbl_power = tk.Label(self.root, text="馬力: 0.0 hp", fg="#ffcc00", bg="#1e1e1e", font=font_main)
        self.lbl_power.pack(anchor="w", padx=10, pady=2)

        self.lbl_torque = tk.Label(self.root, text="扭力: 0.0 Kg·m", fg="#00ccff", bg="#1e1e1e", font=font_main)
        self.lbl_torque.pack(anchor="w", padx=10, pady=2)

        self.lbl_shift = tk.Label(self.root, text="最佳換檔轉速: 偵測中...", fg="#ff3366", bg="#1e1e1e", font=font_highlight)
        self.lbl_shift.pack(anchor="w", padx=10, pady=5)

        # 輪胎打滑率
        self.frame_tires = tk.Frame(self.root, bg='#1e1e1e')
        self.frame_tires.pack(anchor="w", padx=10, pady=0)
        
        self.lbl_tire_fl = tk.Label(self.frame_tires, text="左前: 0%", fg="#ffffff", bg="#1e1e1e", font=font_main, width=12, anchor="w")
        self.lbl_tire_fl.grid(row=0, column=0, padx=5)
        
        self.lbl_tire_fr = tk.Label(self.frame_tires, text="右前: 0%", fg="#ffffff", bg="#1e1e1e", font=font_main, width=12, anchor="w")
        self.lbl_tire_fr.grid(row=0, column=1, padx=5)
        
        self.lbl_tire_rl = tk.Label(self.frame_tires, text="左後: 0%", fg="#ffffff", bg="#1e1e1e", font=font_main, width=12, anchor="w")
        self.lbl_tire_rl.grid(row=1, column=0, padx=5)
        
        self.lbl_tire_rr = tk.Label(self.frame_tires, text="右後: 0%", fg="#ffffff", bg="#1e1e1e", font=font_main, width=12, anchor="w")
        self.lbl_tire_rr.grid(row=1, column=1, padx=5)

        # 重置按鈕
        self.btn_reset = tk.Button(self.root, text="重置動力數據", bg="#444444", fg="#ffffff", font=("Helvetica", 10, "bold"), command=self.reset_peaks)
        self.btn_reset.pack(anchor="e", padx=10, pady=5)

        self.max_kw = 0.0
        self.max_kw_rpm = 0.0
        self.max_torque = 0.0
        self.max_torque_rpm = 0.0

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((UDP_IP, UDP_PORT))
        
        self.running = True
        self.thread = threading.Thread(target=self.receive_telemetry, daemon=True)
        self.thread.start()
    
    #重置按鈕函式
    def reset_peaks(self):
        self.max_kw = 0.0
        self.max_kw_rpm = 0.0
        self.max_torque = 0.0
        self.max_torque_rpm = 0.0
        self.lbl_shift.config(text="最佳換檔轉速: 重新偵測中...", fg="#ff3366")

    #接收遙測數據的主循環
    def receive_telemetry(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(1024)
                packet_len = len(data)
                
                if packet_len >= 323:
                    offset_power = 260
                    offset_torque = 264
                elif packet_len == 311:
                    offset_power = 248
                    offset_torque = 252
                else:
                    continue
                
                current_rpm = struct.unpack_from('<f', data, 16)[0]
                power_watts = struct.unpack_from('<f', data, offset_power)[0]
                torque_nm = struct.unpack_from('<f', data, offset_torque)[0]

                # --- 新增：攔截四輪「綜合打滑率 (Combined Slip)」 ---
                # 偏移量 180~192 位於封包前段的 Sled 區，所有遊戲版本皆通用
                slip_fl = abs(struct.unpack_from('<f', data, 180)[0])
                slip_fr = abs(struct.unpack_from('<f', data, 184)[0])
                slip_rl = abs(struct.unpack_from('<f', data, 188)[0])
                slip_rr = abs(struct.unpack_from('<f', data, 192)[0])

                current_kw = max(0.0, power_watts / 1000.0) * 1.34102209
                current_torque = max(0.0, torque_nm) * 0.10197162129779

                if current_rpm > 2000:
                    if current_kw > self.max_kw:
                        self.max_kw = current_kw
                        self.max_kw_rpm = current_rpm
                    
                    if current_torque > self.max_torque:
                        self.max_torque = current_torque
                        self.max_torque_rpm = current_rpm

                # 透過 after 傳遞給 UI 更新
                self.root.after(0, self.update_ui, current_rpm, current_kw, current_torque, slip_fl, slip_fr, slip_rl, slip_rr)

            except Exception as e:
                print(f"Data error: {e}")

    def update_ui(self, rpm, kw, torque, slip_fl, slip_fr, slip_rl, slip_rr):
        self.lbl_power.config(text=f"馬力: {kw:.1f} hp (峰值: {self.max_kw:.1f} @ {int(self.max_kw_rpm)} RPM)")
        self.lbl_torque.config(text=f"扭力: {torque:.1f} Kg·m (峰值: {self.max_torque:.1f} @ {int(self.max_torque_rpm)} RPM)")
        
        if self.max_kw_rpm > 0:
            shift_rpm = self.max_kw_rpm + 150 
            if rpm >= shift_rpm:
                self.lbl_rpm.config(text=f"轉速 (RPM): {int(rpm)}  ⚠️ 換檔！", fg="#ff0000")
                self.lbl_shift.config(text=f"最佳換檔轉速: {int(shift_rpm)} RPM (已到達!)", fg="#ff0000")
            else:
                self.lbl_rpm.config(text=f"轉速 (RPM): {int(rpm)}", fg="#00ff00")
                self.lbl_shift.config(text=f"最佳換檔轉速: {int(shift_rpm)} RPM", fg="#ff3366")
        else:
            self.lbl_rpm.config(text=f"轉速 (RPM): {int(rpm)}", fg="#00ff00")

        # 建立一個小工具函式來更新單一輪胎的 UI
        def update_tire_label(label, prefix, slip_val):
            slip_pct = int(slip_val * 100)
            # 當打滑率 >= 1.0 (100%) 代表輪胎已經突破抓地力極限
            if slip_val >= 1.0:
                label.config(text=f"{prefix}: {slip_pct}%", fg="#ff3333") # 失去抓地力：紅色警告
            else:
                label.config(text=f"{prefix}: {slip_pct}%", fg="#ffffff") # 正常抓地：白色

        update_tire_label(self.lbl_tire_fl, "左前 (FL)", slip_fl)
        update_tire_label(self.lbl_tire_fr, "右前 (FR)", slip_fr)
        update_tire_label(self.lbl_tire_rl, "左後 (RL)", slip_rl)
        update_tire_label(self.lbl_tire_rr, "右後 (RR)", slip_rr)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ForzaTelemetryOverlay()
    app.run()