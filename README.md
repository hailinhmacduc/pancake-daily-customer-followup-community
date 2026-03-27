# Pancake-silent-reactivator-skill-for-Openclaw

Dự án mã nguồn mở dùng để **chăm sóc lại khách hàng im lặng trên Pancake** mỗi ngày, sử dụng phương pháp kết hợp:
- **Pancake API** để quét các cuộc hội thoại đủ điều kiện
- **Playwright + Chromium CDP** để mở giao diện Pancake thật và gửi tin nhắn follow-up một cách an toàn

Repository này được thiết kế để **chia sẻ công khai trên GitHub**:
- không chứa token thật
- không chứa page ID hay đường dẫn profile riêng tư
- không commit dữ liệu khách hàng
- mọi thông tin nhạy cảm đều do người dùng cung cấp qua biến môi trường

> ## Lưu ý quan trọng
> Đây là **dự án tham khảo**, không phải công cụ growth sẵn dùng.
> Trước khi sử dụng trong thực tế, bạn nên xem xét:
> - Điều khoản dịch vụ của Pancake
> - Chính sách nền tảng Facebook / Meta
> - Quy định về quyền riêng tư và liên hệ khách hàng tại địa phương
> - Quy trình phê duyệt nội bộ của bạn
>
> Bạn chịu trách nhiệm về cách cấu hình, kiểm tra và sử dụng workflow này.

## Dự án này làm gì?

Mỗi lần chạy có thể:
1. Quét các cuộc hội thoại từ một trang Pancake
2. Lọc khách hàng đã im lặng trong `N` ngày
3. Loại trừ cuộc hội thoại có tag bị chặn như `ĐÃ CHỐT` hoặc `KHÔNG MUA`
4. Loại trùng theo Facebook ID của khách hàng
5. Kết nối vào phiên Chromium đã đăng nhập qua CDP
6. Tìm kiếm khách hàng trong giao diện Pancake
7. Bỏ qua comment thread, chỉ gửi khi xác nhận được đây là cuộc trò chuyện Messenger thật
8. Lưu kết quả chạy, trạng thái hàng đợi và trạng thái chống trùng vào file JSON

## Quy tắc nghiệp vụ mặc định

Một cuộc hội thoại đủ điều kiện khi:
- Người gửi cuối cùng là trang/admin
- Cuộc hội thoại cũ hơn `PANCAKE_SCAN_DAYS` ngày (mặc định `2`)
- Tag **không** chứa `ĐÃ CHỐT`
- Tag **không** chứa `KHÔNG MUA`

## Hành vi an toàn

Workflow này được thiết kế thận trọng:
- Nếu giao diện trông giống **comment thread** → bỏ qua
- Nếu kết quả tìm kiếm không thể xác nhận chắc chắn → bỏ qua
- Nếu tin nhắn đã tồn tại trong cuộc trò chuyện → bỏ qua
- Nếu khách hàng đã được gửi ở lần chạy trước → bỏ qua

Mục tiêu: **Thà bỏ sót còn hơn gửi nhầm cuộc hội thoại**.

---

## Cấu trúc dự án

```text
pancake-daily-customer-followup-community/
├─ README.md              # Tài liệu tiếng Anh
├─ README.vi.md           # Tài liệu tiếng Việt (file này)
├─ LICENSE
├─ requirements.txt
├─ .gitignore
├─ config/
│  └─ .env.example
├─ data/
│  └─ .gitkeep
├─ docs/
│  └─ sample-scan-output.json
├─ scripts/
│  ├─ run_followup.sh
│  └─ smoke_test.sh
└─ src/
   └─ pancake_followup.py
```

---

## Yêu cầu hệ thống

- chạy trên thiết bị local
- Python 3.10+
- Chromium đã cài đặt
- Tài khoản Pancake đã đăng nhập trong profile Chromium được chọn
- Quyền truy cập Pancake API cho trang của bạn

## Thông tin người dùng cần cung cấp

Trước khi chạy, bạn cần cung cấp:

### Pancake API
- `PANCAKE_PAGE_ID` — ID trang Pancake
- `PANCAKE_PAGE_ACCESS_TOKEN` — Token truy cập
- `PANCAKE_PAGE_KEY` — Tên gợi nhớ, ví dụ `my-page`
- `PANCAKE_PAGE_URL` — Ví dụ `https://pancake.vn/my-page-slug`

### Trình duyệt / Tự động hóa UI
- Đường dẫn cài đặt Chromium
- Đường dẫn profile Chromium đã đăng nhập Pancake
- Cổng CDP / URL CDP

### Cấu hình nghiệp vụ (tùy chọn)
- Mẫu tin nhắn follow-up
- Số lượng gửi tối đa mỗi lần chạy
- Ngưỡng ngày im lặng
- Vị trí file đầu ra

---

## Cài đặt

### 1. Clone repository

```bash
git clone https://github.com/hailinhmacduc/pancake-daily-customer-followup-community.git
cd pancake-daily-customer-followup-community
```

### 2. Tạo môi trường ảo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. Tạo file `.env`

```bash
cp config/.env.example .env
```

Sau đó điền các giá trị thật vào.

Ví dụ:

```env
PANCAKE_PAGE_KEY=my-page
PANCAKE_PAGE_ID=YOUR_PAGE_ID
PANCAKE_PAGE_ACCESS_TOKEN=YOUR_PAGE_ACCESS_TOKEN
PANCAKE_PAGE_URL=https://pancake.vn/YOUR_PAGE_SLUG

PANCAKE_API_BASE=https://pages.fm/api/public_api
PANCAKE_SCAN_DAYS=2
PANCAKE_LOOKBACK_DAYS=14
PANCAKE_SCAN_LIMIT=100
PANCAKE_MAX_SEND_PER_RUN=5
PANCAKE_MESSAGE_TEMPLATE=Hi anh/chị, em follow up lại cuộc trao đổi trước. Nếu anh/chị vẫn còn quan tâm, em có thể gửi thêm thông tin chi tiết để mình tham khảo nhanh ạ.

PANCAKE_CHROMIUM_PROFILE=$HOME/Library/Application Support/pancake-community-followup
PANCAKE_CHROMIUM_CDP_PORT=9239
PANCAKE_CHROMIUM_CDP_URL=http://127.0.0.1:9239
PANCAKE_CHROMIUM_APP=/Applications/Chromium.app
PANCAKE_CHROMIUM_BIN=/Applications/Chromium.app/Contents/MacOS/Chromium
PANCAKE_PYTHON_BIN=python3
```

### 4. Đăng nhập Pancake trên Chromium

Sử dụng đúng profile Chromium đã cấu hình trong `.env`.

Nếu Chromium chưa chạy với remote debugging, script sẽ tự khởi động.

---

## Cách sử dụng

### A. Chỉ quét (scan)

```bash
set -a && source .env && set +a
python src/pancake_followup.py scan
```

Kết quả JSON bao gồm:
- Tổng số cuộc hội thoại thô
- Số lượng bị loại theo từng quy tắc
- Danh sách ứng viên đủ điều kiện

Xem mẫu đầu ra đã ẩn dữ liệu thật tại: `docs/sample-scan-output.json`

### B. Chạy gửi follow-up hàng ngày

```bash
chmod +x scripts/run_followup.sh
./scripts/run_followup.sh
```

Script sẽ:
1. Đảm bảo Chromium CDP khả dụng
2. Quét ứng viên
3. Tạo hàng đợi gửi
4. Kết nối vào giao diện Pancake
5. Gửi tối đa `PANCAKE_MAX_SEND_PER_RUN` tin nhắn
6. Lưu kết quả vào file JSON

### C. Chạy smoke test

```bash
chmod +x scripts/smoke_test.sh
./scripts/smoke_test.sh
```

Kiểm tra:
- Cú pháp Python của script chính
- Các file tài liệu bắt buộc tồn tại
- `.env.example` chỉ chứa giá trị placeholder
- Không có file JSON runtime nào bị track trong `data/`

---

## File đầu ra

Script tạo ra các file sau trong thư mục `data/`:

| File | Mô tả |
|------|--------|
| `pancake-followup-state.json` | Bộ nhớ chống trùng, khóa pending, lịch sử gửi |
| `pancake-followup-queue.json` | Hàng đợi được tạo cho lần chạy hiện tại |
| `pancake-followup-last-run.json` | Tổng kết lần chạy: danh sách đã gửi, thất bại, bỏ qua |

---

## Tại sao dùng CDP + Chromium thật?

Nhiều workflow Pancake ổn định hơn khi kết nối vào phiên trình duyệt đã đăng nhập thay vì đăng nhập từ đầu trong headless browser mỗi lần.

Lợi ích:
- Tái sử dụng phiên đăng nhập lâu dài
- Dễ debug hơn
- Gần với quy trình vận hành thực tế
- Xác nhận UI an toàn hơn trước khi gửi

---

## Lý do một số ứng viên thất bại

Các lý do thất bại thường gặp:
- `comment_ui_detected_skip` — Phát hiện giao diện comment, bỏ qua
- `no_messenger_candidate_after_search` — Không tìm thấy ứng viên Messenger sau tìm kiếm
- `conversation_search_input_not_found` — Không tìm thấy ô tìm kiếm cuộc hội thoại
- `post_send_message_not_detected_message` — Không xác nhận được tin nhắn sau khi gửi

Đây là các kết quả **an toàn và có chủ đích** trong trường hợp giao diện không rõ ràng.

---

## Quy trình sản xuất khuyến nghị

1. Chạy `scan` trước để xem danh sách ứng viên
2. Kiểm tra thủ công một vài cuộc hội thoại trong giao diện Pancake
3. Đặt `PANCAKE_MAX_SEND_PER_RUN=1` cho lần gửi thử đầu tiên
4. Tăng dần sau khi đã tự tin
5. Giữ lại log và file kết quả để kiểm toán
6. Xem xét nội dung tin nhắn và tần suất liên hệ phù hợp với quy định thị trường

---

## Bảo mật và quyền riêng tư

**KHÔNG** commit các file sau:
- `.env`
- Token truy cập Pancake thật
- Page ID thật (nếu bạn coi là riêng tư)
- File JSON chứa dữ liệu khách hàng
- Profile trình duyệt riêng
- Ảnh chụp màn hình hoặc log chứa tên/tin nhắn khách hàng

Repository đã cấu hình `.gitignore` để bỏ qua các file runtime nhạy cảm, nhưng bạn vẫn nên kiểm tra trước khi push.

---

## Ví dụ cron

Chạy mỗi ngày lúc 13:00:

```cron
0 13 * * * cd /path/to/pancake-daily-customer-followup-community && /bin/bash scripts/run_followup.sh >> /tmp/pancake-followup-cron.log 2>&1
```

---

## Ý tưởng mở rộng

Bạn có thể phát triển thêm:
- Phê duyệt qua Telegram trước khi gửi
- Hỗ trợ nhiều trang cùng lúc
- Cấu hình tag loại trừ linh hoạt
- Chụp ảnh màn hình cho trường hợp thất bại
- Xuất CSV / Google Sheets
- Cơ chế retry và backoff
- Thông báo qua Slack / Discord

---

## Miễn trừ trách nhiệm

Sử dụng có trách nhiệm và tuân thủ:
- Điều khoản của Pancake
- Chính sách nền tảng Facebook
- Quy định quyền riêng tư và liên hệ khách hàng tại địa phương

Hãy kiểm tra mẫu tin nhắn, quy tắc nghiệp vụ và quy trình phê duyệt trước khi bật gửi tự động.

---

## Giấy phép

MIT
