# Bàn giao công việc còn lại của tuần 4

Người bàn giao: Vân. Người nhận: Doanh, Tuyên. Đọc hết file này trước khi chạm vào Pi (khoảng 10 phút).
Kế hoạch gốc và lệnh chi tiết từng bài đo nằm ở `docs/week4_runbook.md`. File này nói: đã làm gì, còn gì, ai làm, lưu ý gì, và **cách biết mình đang làm đúng hay sai**.

## 1. Hiện trạng (27/11, 09:45)

Đã xong (Vân):
- Code, mô hình, công cụ, tài liệu và bản nháp Report week 4 đã có trong repo (nhánh `week4-all`).
- Pi đã được cài bản mới: `web/index.html`, `web/hybrid_abr.js` trong `/var/www/html/`, `abr-health.timer` đã bật, trang `?abr=custom` hiện chữ `custom`.
- Một bản monitor 10 phút (`t17_10min.csv`) đã được bật trên Pi, chạy trong `scripts/`, tự dừng sau 600 s.

CHƯA làm (các số đo trên board): T15, T16, T17 (phân tích), T18, T19, T20, T21, kiểm tra watchdog.
Các ô trong Report week 4 có chữ vàng/nghiêng là chỗ chờ số từ các bài này.

## 2. Phân công đề xuất (đổi được, nhưng ai chạy thì người đó ghi vào Personal contribution)

| Bài | Nội dung | Người làm | Thời gian |
|---|---|---|---|
| T19 | Đồng bộ âm thanh - hình của 3 rendition | Doanh | 20 phút |
| T20 | Frame rớt/trùng, `exposure_dynamic_framerate` bật/tắt | Doanh | 10 phút |
| T21 | PSNR/SSIM (VMAF nếu có) từng rendition, phần cứng vs x264 | Doanh | 15 phút |
| T18 | 1, 2, 3, 5 người xem | Tuyên | 20 phút |
| T17 | Phân tích log ổn định + `NRestarts` | Tuyên | 10 phút |
| Watchdog | `pkill -STOP ffmpeg`, xem Pi tự khởi động lại | Tuyên | 5 phút |
| T15 + T16 | ABR Hybrid so với hls.js mặc định, `tc` 9 x 60 s | Người đang cầm Pi (đề xuất Tuyên) | 25 phút |
| Điền báo cáo | Điền số vào Report week 4 | Vân (sau khi nhận file) | 1 giờ |

Chỉ một người dùng camera một lúc. T20 và T21 **dừng stream**, nên làm sau cùng và không làm khi người khác đang đo.

## 3. Trước khi bắt đầu: kiểm tra nhanh Pi (5 phút)

```bash
ssh g1pi@<IP>                                   # IP hỏi Vân; mật khẩu hỏi Vân (không ghi vào repo)
systemctl is-active abr-hls                     # active
systemctl list-timers | grep abr                # abr-health.timer có mặt
curl -sI http://localhost/hybrid_abr.js | head -1   # HTTP/1.1 200 OK
grep -n "SEG\|GOP" /etc/systemd/system/abr-hls.service   # dòng Environment=SEG=1 và GOP=30 KHÔNG có dấu #
pgrep -fc monitor.sh                            # 1 nếu monitor 10 phút còn chạy, 0 nếu đã xong
```
Nếu `SEG`/`GOP` còn dấu `#`: bỏ dấu `#`, rồi `sudo systemctl daemon-reload && sudo systemctl restart abr-hls`, đợi 1 phút. Nếu không, độ trễ sẽ là 6 giây thay vì 3 giây và số đo không so được với tuần 3.

Lấy code mới nhất về laptop: `git fetch && git checkout week4-all && git pull`. Cần `pip install numpy pandas matplotlib` và `ffmpeg` trên laptop.

## 4. Quy tắc chung (đọc kỹ, đây là chỗ hay sai)

1. **Không sửa số bằng tay.** Số trong báo cáo lấy từ file CSV/log mà công cụ in ra. Không có số thì ghi "chưa đo", không đoán.
2. **Một bài, một thư mục kết quả**, đặt tên theo ID bài: `t19_...`, `t18_...`. Lưu cả file thô (`.csv`, `.mkv`) chứ không chỉ ảnh chụp màn hình.
3. **Ghi lại điều kiện đo** vào file `ghi_chu.txt` trong thư mục đó: ngày giờ, ai đo, mạng nào, có `tc` không, scene quay là gì, trang mở bằng URL nào. Thiếu điều kiện thì số đo vô giá trị.
4. **Đo bài nào xong bài đó, dọn trước khi sang bài khác:** `sudo tc qdisc show dev wlan0` không được còn `tbf`. Nếu còn: `sudo tc qdisc del dev wlan0 root`.
5. **Giữ tab trình duyệt ở phía trước** khi đo trang (tab chạy nền bị trình duyệt làm chậm, log sai).
6. **Đừng dùng SSH qua wlan0 khi `tc` đang giới hạn quá thấp**: phiên SSH có thể giật. Nếu mất kết nối giữa chừng, đợi hết 9 phút `tc` tự dỡ giới hạn, rồi kết nối lại. Không chạy lại ngay.
7. **Làm lại bài hỏng được, nhưng ghi lại lần hỏng** (một dòng trong `ghi_chu.txt`).
8. **Không `git push` thẳng lên `main`.** Đẩy lên nhánh `week4-all` hoặc nhánh riêng, rồi tạo Pull Request.
9. Nếu có kết quả lạ (không giống cột "Kỳ vọng" bên dưới): dừng, ghi lại, hỏi Vân. Đừng làm cho khớp.

## 5. Từng bài: làm gì, kỳ vọng gì, sai thì sao

Lệnh đầy đủ ở `docs/week4_runbook.md`. Ở đây chỉ có các điểm kiểm tra.

### T19 Đồng bộ A/V (Doanh)
Kỳ vọng:
- Mỗi lần ghi 40 s cho ra khoảng 18 cặp sự kiện ("paired").
- `std` của độ lệch nhỏ (thường vài chục ms trở xuống); `trend` gần 0 ms/phút.
- Ba rendition (720p, 540p, 360p) có độ lệch gần nhau, vì cùng một nguồn âm thanh.
- Độ lệch tuyệt đối nằm khoảng vài chục đến vài trăm ms; chuẩn ITU nói -125 đến +45 ms là không nhận ra.

Dấu hiệu sai và cách xử lý:
- Dưới 10 cặp: điện thoại ở xa quá, âm lượng nhỏ, hoặc phòng sáng quá làm camera tự giảm độ sáng. Đưa điện thoại lại gần (30 cm), tăng âm lượng và độ sáng.
- `flash > beep` về số lượng (nhiều chớp, ít bíp): mic không nghe được loa. Để loa sát mic webcam.
- Ba rendition lệch nhau trên 100 ms: ghi lại và báo Vân, có thể là vấn đề timestamp thật.
- Nhớ: số đo gồm cả độ trễ màn hình và loa của điện thoại (khoảng ±50 ms). Ghi điều này vào kết luận.

### T20 Frame rớt/trùng (Doanh)
Kỳ vọng:
- Khi `exposure_dynamic_framerate=0` và đủ sáng: gần 30 fps, thiếu rất ít frame.
- Tuần 3 đo được khoảng 2% frame trùng ở tầng mã hóa; kết quả tầng camera có thể khác.
- Khi `=1` và thiếu sáng (che nửa ống kính): fps có thể tụt rõ, "missing frames" tăng. Đây là điều ta muốn chứng minh.

Dấu hiệu sai:
- `frames` rất ít so với 30 s x 30 fps = 900: kiểm tra stream đã dừng thật (`systemctl is-active abr-hls` phải là `inactive`) và camera không bị chương trình khác giữ.
- Lệnh `v4l2-ctl ... exposure_dynamic_framerate` báo không có control: ghi lại, đó cũng là kết quả (camera này không hỗ trợ).
- Cuối bài phải bật lại stream: `systemctl is-active abr-hls` = `active`.

### T21 Chất lượng từng rendition (Doanh)
Kỳ vọng:
- Với mỗi bộ mã hóa: PSNR và SSIM giảm theo thứ tự 720p > 540p > 360p (vì ảnh được phóng lại về 720p để so).
- `actual_kbps` gần bitrate mục tiêu (2500/1200/500); lệch trên 40% là đáng ngờ.
- `h264_v4l2m2m` (phần cứng) thường kém x264 ở cùng bitrate một chút (slide chương 4 cũng nói vậy). Nếu ngược lại thì ghi nhận, đừng sửa.
- Nếu `ffmpeg -filters | grep libvmaf` không có gì thì chỉ có PSNR/SSIM. Không có VMAF là bình thường, đừng tự tính.

Dấu hiệu sai:
- PSNR 360p cao hơn 720p: thường do cảnh quay quá phẳng (tường trắng). Quay lại cảnh có chuyển động và chi tiết.
- Dòng `skip ... encoder failed`: ghi lại rendition nào bị bỏ.
- Quên `sudo systemctl start abr-hls` ở cuối.

### T18 Nhiều người xem (Tuyên)
Kỳ vọng:
- N=1: tất cả segment 720p, `late 0`, `HTTP errors: 0`.
- Khi N tăng, FFmpeg CPU gần như không đổi (nó mã hóa một lần cho mọi người); `nginx_conn` trong log monitor tăng theo N. Tải tăng ở mạng Wi-Fi, không ở bộ mã hóa.
- Các viewer lệch về rendition thấp hơn khi N lớn là hợp lý.

Dấu hiệu sai:
- `no segments` hoặc nhiều `HTTP errors`: URL sai. Đúng là `http://<IP>/hls/master.m3u8` (mở được bằng trình duyệt hoặc `curl`).
- `viewer_load.py` chạy trên laptop dùng chung card Wi-Fi của laptop: tốc độ từng viewer không đại diện cho Pi; số quan trọng là CPU/băng thông phía Pi trong log monitor.
- Ghi lại giờ bắt đầu mỗi lần chạy để đối chiếu với log monitor.

### T17 Ổn định
Lệnh: `python3 tools/stability_report.py t17_10min.csv`.
Kỳ vọng: `throttling: none`, nhiệt độ dưới 70 °C, `restarts: 0` (log mới có cột này), `HLS RAM disk` phẳng.
Với log dưới 30 phút công cụ in "no leak verdict (run too short)". Đó là đúng. Ghi trong báo cáo: "10-minute stability run", không ghi "1 hour".
Nếu thấy `throttling flags seen` (ví dụ `0x50005`): nguồn điện yếu (under-voltage). Đổi cáp/củ sạc rồi đo lại và ghi lại cả hai lần.
`sampling gap` xuất hiện khi stream bị dừng giữa chừng (ví dụ chạy T20/T21 trong lúc monitor chạy). Làm sai thứ tự thì đo lại.

### T15 và T16 ABR trên board
Kỳ vọng (tuần 3, bản hls.js mặc định, setting B): giảm chất lượng sau 8-9 s, lên lại sau khoảng 64 s, 0 stall, độ trễ khoảng 3.2 s.
Mô hình dự đoán cho Hybrid: giảm sau khoảng 1-5 s, lên lại sau vài giây, 0 stall. Hybrid bắt đầu ở 360p và mất vài giây mới lên 720p.
Kiểm tra đúng trang: dòng thống kê kết thúc bằng `custom` (T15) và `auto` (T16). Nếu T15 vẫn hiện `auto`: `hybrid_abr.js` chưa vào Nginx hoặc trình duyệt dùng bản cũ trong cache (Ctrl+Shift+R).
Dấu hiệu sai:
- `stalls` tăng ở T15: ghi lại, báo Vân. Có phương án đổi tham số (`n_up=5`, `hold=12` trong `web/hybrid_abr.js`), nhưng đổi xong phải đo lại cả 9 bước.
- Lên 720p mà không bao giờ xuống ở bước 2.5 Mbit/s: `tc` không áp dụng. Kiểm tra `sudo tc qdisc show dev wlan0` trong lúc chạy.
- Quên bấm **Clear log** trước khi chạy `tc_steps.sh`, hoặc quên tải CSV sau khi thấy `limit removed on wlan0`.

### Watchdog (Tuyên)
`sudo pkill -STOP ffmpeg`, đợi tối đa 60 s, rồi `journalctl -t abr-health --since "5 min ago"`. Phải thấy dòng "playlist ... old: restarting abr-hls" và stream phải tự quay lại. Nếu 90 giây vẫn chưa quay lại: kiểm tra `TimeoutStopSec=10` đã có trong `/etc/systemd/system/abr-hls.service` (sau đó `daemon-reload`). Kết thúc: `systemctl is-active abr-hls` phải là `active`.

## 6. Gửi kết quả về cho Vân

Gom vào `week4_pi/` (hoặc đẩy lên nhánh riêng trong `data/week4/pi/`):
- T15/T16: 2 file CSV của trang, 2 file `tc_steps_*.csv`.
- T17: `t17_10min.csv` (hoặc `t17_session.csv`), `t17.md`, dòng `NRestarts`.
- T18: các file `t18_*` + phần in ra của `viewer_load.py`.
- T19: 3 file `rec_*.mkv` hoặc phần in ra + `av_*.csv`.
- T20: thư mục `t20/`. T21: `quality_pi.csv`.
- Mỗi bài một `ghi_chu.txt` (điều kiện đo, lần hỏng).

Mỗi người viết 3-5 dòng "Personal contribution" cho phần mình: đã chạy bài nào, thấy gì, sửa gì. Chỉ viết việc đã làm thật và có file làm bằng chứng.

## 7. Trước khi rời Pi

- [ ] `systemctl is-active abr-hls` = `active`; trang mở được và có hình/tiếng
- [ ] `sudo tc qdisc show dev wlan0` không còn `tbf`
- [ ] `pgrep -fc monitor.sh` = 0 (không còn monitor chạy ngầm)
- [ ] `/etc/systemd/system/abr-hls.service` vẫn có `SEG=1`, `GOP=30`
- [ ] Mọi file kết quả đã chép về laptop và đã đẩy lên GitHub
